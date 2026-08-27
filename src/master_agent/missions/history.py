"""What was planned, and what became of it (Mission Brief 037).

A `PlanRecord` is the durable answer to *"what did Kalpavriksha decide to
do, and what actually happened?"* -- one row per mission, one entry per
step, written from the Event Bus as the Runtime works.

## It observes; it never drives

Every field here is filled by a **subscriber**, using the same bus MB034's
memory uses and the same per-event-type subscription discipline. Nothing
in this module dispatches, unlocks, orders or retries anything: Mission
Control owns lifecycle, and a history that could influence execution
would be a second orchestration authority wearing a notebook.

## Replay never contacts a provider

`replay()` reconstructs a mission from recorded evidence alone. There is
no provider, no executor and no gateway anywhere in this module's imports
-- asserted by a test rather than promised here -- because a "replay" that
re-ran the work would answer a different question than the one being
asked, and would spend money doing it.

Everything stored is **JSON-plain**, the discipline `Event.payload` and
`Evidence.observation` already follow. An `ExpectedOutcome` is therefore
recorded as its description and its checks' descriptions, not as the live
object: a record has to survive being written to disk and read by a
process that does not import `verification/`.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# ---- step and mission states --------------------------------------------
#
# Deliberately this module's own small vocabulary rather than Mission
# Control's `TaskState`: a record describes what a founder is shown, and
# importing the frozen enum here would couple the history file format to
# an internal lifecycle enum that is free to grow.

PENDING = "pending"
RUNNING = "running"
COMPLETED = "completed"
FAILED = "failed"

PLANNED = "planned"

#: A step whose dependencies have not all completed yet. Derived, never
#: stored: it is a fact about the *rest* of the plan at read time, and
#: storing it would let it go stale.
BLOCKED = "waiting on dependency"

HISTORY_FILENAME = "plan_history.json"


def _now() -> datetime:
    return datetime.now(UTC)


def _stamp(moment: datetime | None) -> str | None:
    return moment.isoformat() if moment is not None else None


@dataclass
class StepRecord:
    """One planned step, and what became of it."""

    step_id: str
    capability: str
    payload: dict[str, Any] = field(default_factory=dict)
    depends_on: list[str] = field(default_factory=list)
    #: The expectation as text. See the module docstring on why this is
    #: not the live `ExpectedOutcome`.
    expectation: str = ""
    checks: list[str] = field(default_factory=list)
    priority: str = "normal"
    estimated_complexity: str = "moderate"

    state: str = PENDING
    verdict: str = ""
    evidence_id: str | None = None
    #: The canonical JSON projection of the Evidence Verification produced
    #: (`Evidence.as_dict()`), or `None` when this step was verified before
    #: Evidence was retained -- or was never verified at all.
    #:
    #: `evidence_id` is NOT evidence. The id correlates a record; it cannot
    #: say what was observed, when, by which verifier, against what checks,
    #: or which of them failed. Those answers live here.
    evidence: dict[str, Any] | None = None
    #: Destination argument -> binding, as the Planner declared it. Kept so
    #: durable history can answer "where was this input meant to come
    #: from?" alongside `input_provenance`'s "where did it actually come
    #: from?".
    input_bindings: dict[str, Any] = field(default_factory=dict)
    founder_checkpoint: str = ""
    #: The founder requirement ids this step took responsibility for.
    #:
    #: Kept durably so a founder can ask, after the fact, *"did it
    #: actually do what I asked?"* and be answered from what was
    #: recorded rather than from a model re-reading their sentence.
    covers: list[str] = field(default_factory=list)
    #: Why this capability was chosen for those requirements, composed
    #: from planning-time FACTS: the requirement, the capability's own
    #: published description, and its argument contract.
    #:
    #: Recorded rather than reconstructed. A founder asking "why did you
    #: use that tool?" a day later must not be answered by a model
    #: inventing a plausible reason -- the reason existed at planning
    #: time and this is where it survives.
    selection_reason: str = ""
    #: Which step and field actually supplied each bound input, and under
    #: which Evidence, recorded when the step started.
    input_provenance: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    started_at: str | None = None
    ended_at: str | None = None

    @property
    def verified(self) -> bool:
        """MB035's rule, unchanged: `matched` only. A step that completed
        without a verdict is done, not verified."""
        return self.verdict == "matched"

    def as_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "capability": self.capability,
            "payload": dict(self.payload),
            "depends_on": list(self.depends_on),
            "expectation": self.expectation,
            "checks": list(self.checks),
            "priority": self.priority,
            "estimated_complexity": self.estimated_complexity,
            "state": self.state,
            "verdict": self.verdict,
            "evidence_id": self.evidence_id,
            "evidence": self.evidence,
            "input_bindings": dict(self.input_bindings),
            "founder_checkpoint": self.founder_checkpoint,
            "covers": list(self.covers),
            "selection_reason": self.selection_reason,
            "input_provenance": list(self.input_provenance),
            "errors": list(self.errors),
            "started_at": self.started_at,
            "ended_at": self.ended_at,
        }

    @classmethod
    def from_dict(cls, document: dict[str, Any]) -> StepRecord:
        return cls(
            step_id=document["step_id"],
            capability=document.get("capability", ""),
            payload=dict(document.get("payload") or {}),
            depends_on=list(document.get("depends_on") or []),
            expectation=document.get("expectation", ""),
            checks=list(document.get("checks") or []),
            priority=document.get("priority", "normal"),
            estimated_complexity=document.get("estimated_complexity", "moderate"),
            state=document.get("state", PENDING),
            verdict=document.get("verdict", ""),
            evidence_id=document.get("evidence_id"),
            # `.get` with no default: a record written before Evidence was
            # retained loads with `None`, which is the truth about it. It is
            # never synthesised from `evidence_id` -- an id is not evidence.
            evidence=document.get("evidence"),
            input_bindings=document.get("input_bindings") or {},
            founder_checkpoint=document.get("founder_checkpoint") or "",
            covers=list(document.get("covers") or []),
            selection_reason=document.get("selection_reason") or "",
            input_provenance=document.get("input_provenance") or [],
            errors=list(document.get("errors") or []),
            started_at=document.get("started_at"),
            ended_at=document.get("ended_at"),
        )


@dataclass
class PlanRecord:
    """One mission: the plan, and its progress."""

    plan_id: str
    objective: str
    steps: list[StepRecord] = field(default_factory=list)
    #: What the founder required, as the Intent Layer extracted it.
    #:
    #: The other half of the semantic trace. Coverage on a step says
    #: which requirement it answered for; this says what the
    #: requirements WERE, so the pair can be read back without the
    #: original sentence being re-interpreted by anything.
    requirements: list[dict[str, Any]] = field(default_factory=list)
    state: str = PLANNED
    planned_at: str = ""
    finished_at: str | None = None
    #: Who produced the plan, and the Broker ledger entry that chose them.
    #: Recorded so "which provider planned this?" is answerable from the
    #: record rather than by correlating timestamps.
    planned_by: str | None = None
    entry_id: int | None = None
    #: WHY this mission was planned the way it was. `planned_by` already
    #: answered "which provider planned this?"; these answer the question
    #: underneath it -- whether a provider was asked at all, and on what
    #: grounds.
    #:
    #: `selected_mode` is the founder's LOCAL / AI MODE / BOTH choice at
    #: plan time. `effective_mode` is what the mission actually ran under;
    #: they differ when the objective needed resources the selection did
    #: not name, and `mode_reason` says which resource forced it. A
    #: deterministic local plan records a provider of `None` and a mode
    #: pair that explains why nothing was asked -- which is precisely the
    #: fact an FMEA pass needs and could not previously recover.
    selected_mode: str = ""
    effective_mode: str = ""
    mode_reason: str = ""
    #: The reasoning ladder's attempt sequence, in order, when a provider
    #: was asked at all. `planned_by` names the provider that ANSWERED;
    #: this names the ones tried before it and why they did not. Empty for
    #: a deterministic plan, which asked nobody -- and that emptiness is
    #: itself the answer to "did this mission use AI?".
    attempts: list[dict[str, Any]] = field(default_factory=list)

    # ---- derived reads --------------------------------------------------

    def step(self, step_id: str) -> StepRecord | None:
        for record in self.steps:
            if record.step_id == step_id:
                return record
        return None

    @property
    def completed(self) -> list[StepRecord]:
        return [s for s in self.steps if s.state == COMPLETED]

    @property
    def failed(self) -> list[StepRecord]:
        return [s for s in self.steps if s.state == FAILED]

    @property
    def running(self) -> list[StepRecord]:
        return [s for s in self.steps if s.state == RUNNING]

    @property
    def remaining(self) -> list[StepRecord]:
        return [s for s in self.steps if s.state in (PENDING, RUNNING)]

    @property
    def current(self) -> StepRecord | None:
        """What is happening now, or what is next.

        A running step if there is one; otherwise the first step that
        could start. Never a blocked step presented as current -- being
        stuck behind a dependency is a different thing from being next,
        and MB029 established that the founder page must not blur two
        states into one word.
        """
        running = self.running
        if running:
            return running[0]
        for record in self.steps:
            if record.state == PENDING and self.is_ready(record):
                return record
        return None

    def is_ready(self, record: StepRecord) -> bool:
        return all(
            (self.step(dependency) or StepRecord(dependency, "")).state == COMPLETED
            for dependency in record.depends_on
        )

    @property
    def blocked(self) -> list[StepRecord]:
        """Pending steps waiting on a dependency that has not completed."""
        return [s for s in self.steps if s.state == PENDING and not self.is_ready(s)]

    @property
    def unverified(self) -> list[StepRecord]:
        """Completed steps with no `matched` verdict.

        Worth its own read: MB035 draws a line between *not checked* and
        *not matched*, and a plan where every step completed but nothing
        was verified is not a successful mission -- it is an unmeasured
        one.
        """
        return [s for s in self.completed if not s.verified]

    @property
    def progress(self) -> float:
        if not self.steps:
            return 0.0
        return len(self.completed) / len(self.steps)

    def as_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "objective": self.objective,
            "state": self.state,
            "planned_at": self.planned_at,
            "finished_at": self.finished_at,
            "planned_by": self.planned_by,
            "entry_id": self.entry_id,
            "selected_mode": self.selected_mode,
            "effective_mode": self.effective_mode,
            "mode_reason": self.mode_reason,
            "attempts": [dict(a) for a in self.attempts],
            "steps": [record.as_dict() for record in self.steps],
            "requirements": [dict(r) for r in self.requirements],
        }

    @classmethod
    def from_dict(cls, document: dict[str, Any]) -> PlanRecord:
        return cls(
            plan_id=document["plan_id"],
            objective=document.get("objective", ""),
            steps=[StepRecord.from_dict(row) for row in document.get("steps") or []],
            requirements=[dict(r) for r in document.get("requirements") or []],
            state=document.get("state", PLANNED),
            planned_at=document.get("planned_at", ""),
            finished_at=document.get("finished_at"),
            planned_by=document.get("planned_by"),
            entry_id=document.get("entry_id"),
            # Absent in records written before routing was recorded. An
            # older history stays readable and simply reports the routing
            # it never captured as unknown, rather than failing to load.
            selected_mode=document.get("selected_mode", ""),
            effective_mode=document.get("effective_mode", ""),
            mode_reason=document.get("mode_reason", ""),
            attempts=[dict(a) for a in (document.get("attempts") or [])],
        )


# ---- replay --------------------------------------------------------------


@dataclass(frozen=True)
class ReplayStep:
    """One step as it happened, reconstructed from the record."""

    order: int
    step_id: str
    capability: str
    payload: dict[str, Any]
    expectation: str
    state: str
    verdict: str
    evidence_id: str | None
    errors: tuple[str, ...] = ()

    @property
    def verified(self) -> bool:
        return self.verdict == "matched"


@dataclass(frozen=True)
class Replay:
    """A mission, re-read rather than re-run."""

    plan_id: str
    objective: str
    steps: tuple[ReplayStep, ...] = ()
    state: str = PLANNED
    planned_by: str | None = None
    #: False when the mission has not finished, so a reader is never
    #: shown a partial history as though it were the whole story.
    complete: bool = False

    @property
    def verified_steps(self) -> tuple[ReplayStep, ...]:
        return tuple(step for step in self.steps if step.verified)

    @property
    def evidence_ids(self) -> tuple[str, ...]:
        return tuple(step.evidence_id for step in self.steps if step.evidence_id)

    def as_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "objective": self.objective,
            "state": self.state,
            "complete": self.complete,
            "planned_by": self.planned_by,
            "steps": [
                {
                    "order": step.order,
                    "step_id": step.step_id,
                    "capability": step.capability,
                    "payload": dict(step.payload),
                    "expectation": step.expectation,
                    "state": step.state,
                    "verdict": step.verdict,
                    "evidence_id": step.evidence_id,
                    "errors": list(step.errors),
                }
                for step in self.steps
            ],
        }


# ---- stores --------------------------------------------------------------


class InMemoryPlanStore:
    """The default. Loses history on exit, which is correct for a test and
    honest for a process that was never asked to persist."""

    def __init__(self) -> None:
        self._records: dict[str, PlanRecord] = {}

    def load(self) -> dict[str, PlanRecord]:
        return dict(self._records)

    def save(self, records: dict[str, PlanRecord]) -> None:
        self._records = dict(records)


class JsonFilePlanStore:
    """One JSON file, rewritten whole.

    A corrupt file is **moved aside, never overwritten** -- MB034's rule,
    and for the same reason: a founder can open a `.corrupt` file and read
    what their system did; they cannot recover a file the program
    replaced.
    """

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.problems: list[str] = []

    def load(self) -> dict[str, PlanRecord]:
        if not self.path.exists():
            return {}
        try:
            document = json.loads(self.path.read_text(encoding="utf-8"))
            rows = document["plans"]
            records = [PlanRecord.from_dict(row) for row in rows]
        except (ValueError, TypeError, KeyError, OSError) as exc:
            self._set_aside(exc)
            return {}
        return {record.plan_id: record for record in records}

    def _set_aside(self, exc: Exception) -> None:
        spoiled = self.path.with_suffix(self.path.suffix + ".corrupt")
        try:
            self.path.replace(spoiled)
            self.problems.append(f"unreadable history moved to {spoiled.name}: {exc}")
        except OSError as move_failure:  # pragma: no cover - platform-specific
            self.problems.append(f"unreadable history could not be moved: {move_failure}")

    def save(self, records: dict[str, PlanRecord]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        document = {"version": 1, "plans": [r.as_dict() for r in records.values()]}
        self.path.write_text(json.dumps(document, indent=2), encoding="utf-8")


# ---- the history ---------------------------------------------------------


class PlanHistory:
    """Every plan this system has produced, and how each one went."""

    def __init__(self, store: Any = None, clock: Any = None) -> None:
        self._store = store if store is not None else InMemoryPlanStore()
        self._clock = clock or _now
        self._records: dict[str, PlanRecord] = self._store.load()

    # ---- writing --------------------------------------------------------

    def record_plan(
        self,
        plan_id: str,
        objective: str,
        plan: Any,
        planned_by: str | None = None,
        entry_id: int | None = None,
        selected_mode: str = "",
        effective_mode: str = "",
        mode_reason: str = "",
        attempts: Any = (),
    ) -> PlanRecord:
        """Write the plan as planned, before anything runs.

        Deliberately not "write it when it finishes": a mission that dies
        halfway must still be answerable for what it *intended*, and a
        history that only records successes is a marketing document.
        """
        record = PlanRecord(
            plan_id=plan_id,
            objective=objective,
            planned_at=_stamp(self._clock()) or "",
            planned_by=planned_by,
            selected_mode=selected_mode,
            effective_mode=effective_mode,
            mode_reason=mode_reason,
            attempts=[dict(a) for a in (attempts or ())],
            entry_id=entry_id,
            steps=[_step_record(step) for step in plan.steps],
            requirements=[r.as_dict() for r in getattr(plan, "requirements", ()) or ()],
        )
        self._records[plan_id] = record
        self._flush()
        return record

    def attach_to(self, mission_control: Any) -> tuple[str, ...]:
        """Subscribe to the events that change a mission's story.

        Per event type, never to everything: the Runtime publishes a
        heartbeat every cycle, and MB034 already learned what subscribing
        to all of it costs.
        """
        from master_agent.mission_control.events import EventType

        wiring = (
            (EventType.TASK_STARTED, self._on_task_started),
            (EventType.TASK_COMPLETED, self._on_task_completed),
            (EventType.TASK_FAILED, self._on_task_failed),
            (EventType.VERIFICATION_COMPLETED, self._on_verification),
            (EventType.OBJECTIVE_COMPLETED, self._on_objective_completed),
            (EventType.OBJECTIVE_FAILED, self._on_objective_failed),
        )
        for event_type, handler in wiring:
            mission_control.bus.subscribe(handler, event_type)
        return tuple(event_type.value for event_type, _ in wiring)

    # ---- event handlers -------------------------------------------------

    def _locate(self, event: Any) -> tuple[PlanRecord, StepRecord] | None:
        """The plan and step this event is about, or nothing.

        An event for work this history never planned is ignored in
        silence. That is the common case, not an anomaly: the launcher
        submits a machine-scan objective at every boot, and it did not
        come from the Planner.
        """
        record = self._records.get(event.objective_id or "")
        if record is None:
            return None
        step = record.step(event.task_id or "")
        if step is None:
            return None
        return record, step

    def _on_task_started(self, event: Any) -> None:
        found = self._locate(event)
        if found is None:
            return
        record, step = found
        step.state = RUNNING
        step.started_at = _stamp(self._clock())
        provenance = (event.payload or {}).get("input_provenance")
        if isinstance(provenance, list) and provenance:
            # Where each bound input actually came from, recorded at the
            # moment it was used. Nothing is filled in for a step that
            # declared no bindings.
            step.input_provenance = list(provenance)
        record.state = RUNNING
        self._flush()

    def _on_task_completed(self, event: Any) -> None:
        found = self._locate(event)
        if found is None:
            return
        _record, step = found
        step.state = COMPLETED
        step.ended_at = _stamp(self._clock())
        evidence_id = (event.payload or {}).get("evidence_id")
        if evidence_id:
            step.evidence_id = evidence_id
        self._flush()

    def _on_task_failed(self, event: Any) -> None:
        found = self._locate(event)
        if found is None:
            return
        _record, step = found
        step.state = FAILED
        step.ended_at = _stamp(self._clock())
        error = event.error or (event.payload or {}).get("error")
        if error and error not in step.errors:
            step.errors.append(str(error))
        self._flush()

    def _on_verification(self, event: Any) -> None:
        found = self._locate(event)
        if found is None:
            return
        _record, step = found
        payload = event.payload or {}
        step.verdict = str(payload.get("verdict") or "")
        step.evidence_id = payload.get("evidence_id") or step.evidence_id
        # Stored exactly as Verification produced it. Nothing is filled in
        # for an event that carries none: a step verified before this
        # existed truthfully has no Evidence, and inventing one from the id
        # would be fabrication.
        evidence = payload.get("evidence")
        if isinstance(evidence, dict):
            step.evidence = dict(evidence)
        self._flush()

    def _on_objective_completed(self, event: Any) -> None:
        self._finish(event.objective_id, COMPLETED)

    def _on_objective_failed(self, event: Any) -> None:
        self._finish(event.objective_id, FAILED)

    def _finish(self, plan_id: str | None, state: str) -> None:
        record = self._records.get(plan_id or "")
        if record is None:
            return
        record.state = state
        record.finished_at = _stamp(self._clock())
        self._flush()

    def _flush(self) -> None:
        self._store.save(self._records)

    # ---- reading --------------------------------------------------------

    def all(self) -> tuple[PlanRecord, ...]:
        return tuple(self._records.values())

    def get(self, plan_id: str) -> PlanRecord | None:
        return self._records.get(plan_id)

    def latest(self) -> PlanRecord | None:
        records = self.all()
        return records[-1] if records else None

    def current(self) -> PlanRecord | None:
        """The mission in flight, or the most recent one.

        A founder asking "what is it doing?" while nothing runs should see
        what it just did, not a blank panel.
        """
        for record in reversed(self.all()):
            if record.state in (PLANNED, RUNNING):
                return record
        return self.latest()

    # ---- replay ---------------------------------------------------------

    def replay(self, plan_id: str) -> Replay | None:
        """Re-read a mission. Contacts nothing.

        The order is the order the plan was recorded in, which MB036's
        topological sort already made an executable order -- reconstructing
        it here would be a second opinion about a question that was
        settled when the plan was written.
        """
        record = self._records.get(plan_id)
        if record is None:
            return None
        return Replay(
            plan_id=record.plan_id,
            objective=record.objective,
            state=record.state,
            planned_by=record.planned_by,
            complete=record.state in (COMPLETED, FAILED),
            steps=tuple(
                ReplayStep(
                    order=index + 1,
                    step_id=step.step_id,
                    capability=step.capability,
                    payload=dict(step.payload),
                    expectation=step.expectation,
                    state=step.state,
                    verdict=step.verdict,
                    evidence_id=step.evidence_id,
                    errors=tuple(step.errors),
                )
                for index, step in enumerate(record.steps)
            ),
        )


def _step_record(step: Any) -> StepRecord:
    expected = getattr(step, "expected_outcome", None)
    return StepRecord(
        step_id=step.step_id,
        capability=step.capability,
        payload=dict(step.payload),
        depends_on=list(step.depends_on),
        input_bindings=dict(getattr(step, "input_bindings", None) or {}),
        founder_checkpoint=str(getattr(step, "founder_checkpoint", "") or ""),
        expectation=getattr(expected, "description", "") or "",
        checks=[check.description for check in getattr(expected, "checks", ())],
        priority=getattr(step, "priority", "normal"),
        estimated_complexity=getattr(step, "estimated_complexity", "moderate"),
        covers=list(getattr(step, "covers", ()) or ()),
        selection_reason=str(getattr(step, "selection_reason", "") or ""),
    )
