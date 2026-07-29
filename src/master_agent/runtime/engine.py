"""RuntimeEngine — the loop that replaces the founder in the cycle.

Observe -> Dispatch -> Execute -> Verify -> Report -> Idle -> repeat, until
stopped. See RUNTIME_ENGINE_ARCHITECTURE.md.

What this class does NOT do, deliberately:
  - It performs no work. Every invocation goes through an
    ExecutiveGateway, which is the thing that performs.
  - It knows no Executive. It routes by the Executive ID Mission Control
    assigned; it never imports, names, or queries a concrete Executive.
  - It never re-plans, reorders, substitutes a capability, or edits a
    payload. Retry is mechanical (same task, same payload, bounded);
    anything beyond that is strategic recovery and belongs to the Brain
    (Constitution §11).
  - It never computes a verdict. It asks the gateway to verify and
    forwards the result.
"""
from __future__ import annotations

import threading
import time
from datetime import UTC, datetime
from typing import Any

from master_agent.mission_control.events import (
    MISSION_CONTROL_SOURCE,
    Event,
    EventType,
)
from master_agent.mission_control.mission_control import MissionControl
from master_agent.mission_control.tasks import Task, TaskState
from master_agent.runtime.approval import ApprovalDenied, ApprovalGate, ApprovalRequest
from master_agent.runtime.checkpoint import CheckpointSink, RuntimeCheckpoint
from master_agent.runtime.config import RuntimeConfig
from master_agent.runtime.gateway import ExecutiveGateway, GatewayResult
from master_agent.runtime.health import RuntimeHealth
from master_agent.runtime.states import RuntimeState, assert_transition

RUNTIME_SOURCE = "runtime_engine"


class UnknownGateway(Exception):
    """Raised when Mission Control assigned a task to an Executive the
    Runtime has no gateway for -- a wiring error, surfaced loudly rather
    than silently skipping the task."""


class RuntimeEngine:
    def __init__(
        self,
        mission_control: MissionControl,
        config: RuntimeConfig | None = None,
        clock: Any = None,
        sleep: Any = None,
        checkpoint_sink: CheckpointSink | None = None,
        approval_gate: ApprovalGate | None = None,
    ) -> None:
        self._mc = mission_control
        self._config = config or RuntimeConfig()
        # MB028.0 / ADR-0019: the approval boundary. Consulted once, at
        # the single funnel in `_handle_task()`, before any gateway is
        # touched. `None` means **fail closed** -- see `_require_approval`.
        # A protocol defined inside `runtime/` (approval.py), so the
        # Runtime consults a boundary without depending on the Permission
        # System, exactly as `CheckpointSink` lets it checkpoint without
        # depending on storage.
        self._approval_gate = approval_gate
        # Rule 3: the Runtime *requests* checkpoints through a protocol it
        # defines (runtime/checkpoint.py); it never performs storage.
        self._checkpoint_sink = checkpoint_sink
        # Injected so tests can run a hundred cycles without waiting a
        # hundred seconds, and so uptime is deterministic under test.
        self._clock = clock or (lambda: datetime.now(UTC))
        self._sleep = sleep or time.sleep

        self._gateways: dict[str, ExecutiveGateway] = {}
        self._state = RuntimeState.INITIALIZING
        self._started_at: datetime | None = None
        # `_cycle` is cumulative across restarts (restored from a
        # checkpoint), because "how many cycles has this system ever run"
        # is the useful health number. `_cycles_this_process` is what
        # `max_cycles` bounds -- otherwise a runtime restored at cycle N
        # with max_cycles=N would break out immediately and silently do
        # nothing, which is exactly what a bounded run after a restart
        # must not do. Found by MB025's repeated-restart test.
        self._cycle = 0
        self._cycles_this_process = 0
        self._stop_requested = threading.Event()
        self._thread: threading.Thread | None = None

        self._last_dispatch_at: datetime | None = None
        self._last_verification_at: datetime | None = None
        self._tasks_completed = 0
        self._tasks_failed = 0
        self._retries_performed = 0
        self._escalations = 0

    # ---- wiring ------------------------------------------------------

    def register_gateway(self, executive_id: str, gateway: ExecutiveGateway) -> None:
        """Bind an Executive ID to the thing that can actually run its
        work. The Runtime never learns what that thing is."""
        self._gateways[executive_id] = gateway

    @property
    def state(self) -> RuntimeState:
        return self._state

    # ---- checkpointing (MB025) ---------------------------------------

    def checkpoint(self) -> RuntimeCheckpoint:
        """Capture resumable state. Pure: builds a value object and hands
        it to the sink, if one was provided. A sink that raises must never
        take down the loop -- losing a checkpoint is bad, but stopping the
        heartbeat over it is worse."""
        snapshot = RuntimeCheckpoint(
            state=self._state,
            cycle=self._cycle,
            tasks_completed=self._tasks_completed,
            tasks_failed=self._tasks_failed,
            retries_performed=self._retries_performed,
            escalations=self._escalations,
            last_dispatch_at=self._last_dispatch_at,
            last_verification_at=self._last_verification_at,
        )
        if self._checkpoint_sink is not None:
            try:
                self._checkpoint_sink.save_checkpoint(snapshot)
            except Exception as exc:  # noqa: BLE001 — see docstring
                self._publish(
                    EventType.RUNTIME_ERROR, error=f"checkpoint failed: {exc}"
                )
        return snapshot

    def restore_from(self, checkpoint: RuntimeCheckpoint) -> None:
        """Resume counters from a previous process.

        The runtime state itself is deliberately NOT restored to whatever
        it was mid-cycle: a restored Runtime always comes back through
        INITIALIZING -> IDLE and re-observes Mission Control, because
        whatever it was doing did not finish and must not be assumed to
        have.
        """
        self._cycle = checkpoint.cycle
        self._tasks_completed = checkpoint.tasks_completed
        self._tasks_failed = checkpoint.tasks_failed
        self._retries_performed = checkpoint.retries_performed
        self._escalations = checkpoint.escalations
        self._last_dispatch_at = checkpoint.last_dispatch_at
        self._last_verification_at = checkpoint.last_verification_at

    @property
    def config(self) -> RuntimeConfig:
        return self._config

    # ---- lifecycle ---------------------------------------------------

    def start_background(self) -> None:
        """Run the loop on a background thread. `stop()` joins it."""
        if self._thread is not None:
            raise RuntimeError("runtime is already running")
        self._thread = threading.Thread(target=self.run_forever, daemon=True)
        self._thread.start()

    def run_forever(self) -> None:
        self._begin()
        try:
            while not self._stop_requested.is_set():
                if (
                    self._config.max_cycles is not None
                    and self._cycles_this_process >= self._config.max_cycles
                ):
                    break
                self._run_cycle()
                if not self._stop_requested.is_set():
                    self._sleep(self._config.poll_interval_seconds)
        finally:
            self._shutdown()

    def run_once(self) -> list[Task]:
        """One cycle, synchronously. The unit of the loop, exposed so a
        cycle can be tested without threads or timing."""
        if self._state is RuntimeState.INITIALIZING:
            self._begin()
        return self._run_cycle()

    def stop(self, timeout: float | None = None) -> None:
        """Request graceful shutdown: the loop finishes the task it is on,
        then stops. Bounded by shutdown_timeout_seconds."""
        self._stop_requested.set()
        if self._thread is not None:
            self._thread.join(timeout or self._config.shutdown_timeout_seconds)
            self._thread = None
        elif self._state not in {RuntimeState.STOPPED, RuntimeState.STOPPING}:
            # Synchronous caller (run_once style) -- shut down in place so
            # the state machine and the shutdown event still happen.
            self._shutdown()

    def _begin(self) -> None:
        self._started_at = self._clock()
        self._transition(RuntimeState.IDLE)
        self._publish(
            EventType.RUNTIME_STARTED,
            payload={
                "poll_interval_seconds": self._config.poll_interval_seconds,
                "max_attempts": self._config.max_attempts,
                "gateways": sorted(self._gateways),
            },
        )

    def _shutdown(self) -> None:
        if self._state is RuntimeState.STOPPED:
            return
        if self._state is not RuntimeState.STOPPING:
            self._transition(RuntimeState.STOPPING)
            self._publish(EventType.RUNTIME_STOPPING)
        self._transition(RuntimeState.STOPPED)
        # The final snapshot goes into the immutable Audit Stream, and --
        # since Mission Brief 025 -- through the checkpoint sink to
        # durable storage as well, so a graceful shutdown is the cleanest
        # possible restart point.
        self._publish(EventType.RUNTIME_STOPPED, payload=self.health().as_dict())
        self.checkpoint()

    # ---- one cycle ---------------------------------------------------

    def _run_cycle(self) -> list[Task]:
        self._cycle += 1
        self._cycles_this_process += 1
        handled: list[Task] = []

        try:
            self._transition(RuntimeState.DISPATCHING)
            self._publish(EventType.DISPATCH_STARTED, payload={"cycle": self._cycle})

            tasks = self._dispatch()
            if not tasks:
                self._go_idle(reason="no work ready")
                return []

            self._last_dispatch_at = self._clock()
            for task in tasks[: self._config.max_concurrent_tasks]:
                self._handle_task(task)
                handled.append(task)

            self._go_idle(reason="cycle complete")
        except Exception as exc:  # noqa: BLE001 — a runtime that dies on one bad cycle is not a heartbeat
            self._publish(EventType.RUNTIME_ERROR, error=f"cycle {self._cycle} failed: {exc}")
            self._recover()
        finally:
            # Checkpoint at the end of every cycle, including a failed one
            # -- a cycle that went wrong is exactly when the state is most
            # worth having on disk.
            self.checkpoint()

        return handled

    def _dispatch(self) -> list[Task]:
        """Ask Mission Control what is ready across every objective. The
        Runtime never inspects an Executive to decide this."""
        assigned: list[Task] = []
        for objective in self._mc.dispatcher.objectives():
            assigned.extend(self._mc.dispatch_ready(objective.objective_id))
        return assigned

    def _handle_task(self, task: Task) -> None:
        gateway = self._gateways.get(task.assigned_executive or "")
        if gateway is None:
            message = (
                f"no gateway registered for executive "
                f"'{task.assigned_executive}' (task {task.task_id})"
            )
            self._publish(EventType.RUNTIME_ERROR, task_id=task.task_id, error=message)
            self._report_failure(task, message)
            return

        # Mission Control speaks qualified names ("Filesystem.CreateFolder");
        # an Executive speaks its own local ones ("create_folder"). The
        # translation is resolved *through Mission Control*, which stores
        # both on the capability descriptor -- never by un-mangling the
        # string, which would be lossy, and never by asking the Executive,
        # which Rule 2 forbids.
        try:
            local_capability = self._mc.capabilities.get(task.capability).capability
        except Exception as exc:  # noqa: BLE001 — an unresolvable capability is a failed task, not a dead loop
            self._report_failure(task, f"could not resolve capability: {exc}")
            return

        # ---- THE APPROVAL BOUNDARY (MB028.0, ADR-0019) ----------------
        # Everything below this line executes. Nothing above it does. This
        # is the only place in the Runtime where a gateway is reached, so
        # this is the only place a boundary is needed -- and the only
        # place one can be bypassed, which is why it is here and not
        # inside any gateway implementation.
        try:
            self._require_approval(task, local_capability)
        except ApprovalDenied as denied:
            self._refuse(task, denied)
            return

        self._transition(RuntimeState.WAITING)
        self._mc.task_started(task.task_id, objective_id=self._objective_of(task))

        result = self._execute_with_retry(gateway, task, local_capability)

        if not result.success:
            self._escalate(task, result.error_text)
            return

        evidence = self._verify(gateway, task, local_capability)

        # Execution succeeding never implies the mission step succeeded:
        # a NOT_MATCHED verdict is a failure, because ADR-0011 exists
        # precisely to keep those two claims separate.
        if evidence is not None and evidence.verdict.value != "matched":
            self._report_failure(
                task,
                f"verification verdict was '{evidence.verdict.value}'",
                evidence_id=evidence.evidence_id,
            )
            return

        self._mc.task_completed(
            task.task_id,
            result=result.output,
            evidence_id=evidence.evidence_id if evidence else None,
            objective_id=self._objective_of(task),
        )
        self._tasks_completed += 1

    def _execute_with_retry(
        self, gateway: ExecutiveGateway, task: Task, local_capability: str
    ) -> GatewayResult:
        """Mechanical retry only: identical capability, identical payload,
        bounded attempts, fixed delay. Mission Control is told nothing
        until the final attempt resolves, which is what keeps its own
        "the dispatcher never auto-retries" guarantee literally true."""
        last: GatewayResult = GatewayResult(success=False, errors=["no attempt was made"])

        for attempt in range(1, self._config.max_attempts + 1):
            try:
                last = gateway.invoke(local_capability, dict(task.payload))
            except Exception as exc:  # noqa: BLE001 — a gateway that raises is a failed attempt, not a dead runtime
                last = GatewayResult(success=False, errors=[f"gateway raised: {exc}"])

            if last.success:
                return last

            if attempt < self._config.max_attempts:
                self._retries_performed += 1
                self._transition(RuntimeState.RECOVERING)
                self._publish(
                    EventType.TASK_RETRY_SCHEDULED,
                    task_id=task.task_id,
                    capability=task.capability,
                    payload={"attempt": attempt, "of": self._config.max_attempts},
                    error=last.error_text,
                )
                self._sleep(self._config.retry_delay_seconds)
                self._transition(RuntimeState.WAITING)

        return last

    def _verify(
        self, gateway: ExecutiveGateway, task: Task, local_capability: str
    ) -> Any:
        expected = task.expected_outcome
        if expected is None or not self._config.verify_when_expected_outcome_present:
            return None

        self._transition(RuntimeState.VERIFYING)
        objective_id = self._objective_of(task)
        self._mc.verification_started(task.task_id, objective_id=objective_id)

        evidence = gateway.verify(local_capability, dict(task.payload), expected)
        self._last_verification_at = self._clock()

        if evidence is None:
            # An Executive with no Verifier produces no Evidence. Recorded
            # honestly rather than treated as a pass.
            self._publish(
                EventType.VERIFICATION_COMPLETED,
                task_id=task.task_id,
                capability=task.capability,
                payload={"verdict": None, "evidence_id": None, "verifier": "none"},
            )
            return None

        self._mc.verification_completed(
            task.task_id,
            verdict=evidence.verdict.value,
            evidence_id=evidence.evidence_id,
            objective_id=objective_id,
        )
        return evidence

    # ---- failure handling -------------------------------------------

    def _require_approval(self, task: Task, local_capability: str) -> None:
        """Consult the approval boundary. Raises `ApprovalDenied`.

        **Fails closed.** A Runtime with no gate refuses *everything* --
        not merely everything above `READ_ONLY`. The Runtime cannot know a
        capability's risk tier (that is the gate's job, precisely so the
        Runtime stays ignorant of Executives, MB024 Rule 2), so it cannot
        safely make an exception it is unable to evaluate. Forgetting to
        wire a gate therefore yields a system that does nothing, never one
        that does everything -- which is what makes Constitution Rule 5 an
        architectural fact here rather than a convention.
        """
        request = ApprovalRequest(
            executive_id=task.assigned_executive or "",
            qualified_capability=task.capability,
            local_capability=local_capability,
            task_id=task.task_id,
            objective_id=self._objective_of(task),
        )
        if self._approval_gate is None:
            raise ApprovalDenied(
                request,
                "no approval gate is wired; the Runtime refuses to execute",
            )
        self._approval_gate.check(request)

    def _refuse(self, task: Task, denied: ApprovalDenied) -> None:
        """A refusal is not a failure of the work -- it is the system
        working. Published as `APPROVAL_REQUIRED` (the founder-facing
        signal that something is waiting on them) and reported as a failed
        task so it surfaces in Founder State rather than vanishing.

        Never retried: `_execute_with_retry` is not reached, because
        retrying a refusal would be asking the same question repeatedly
        and hoping for a different answer.
        """
        self._publish(
            EventType.APPROVAL_REQUIRED,
            task_id=task.task_id,
            objective_id=denied.request.objective_id,
            capability=task.capability,
            payload=denied.request.as_dict(),
            error=denied.reason,
        )
        self._report_failure(task, f"approval denied: {denied.reason}")

    def _escalate(self, task: Task, error: str) -> None:
        """Attempts exhausted. The Runtime reports and stops -- it does not
        decide what happens next; that is the Brain's, and no Brain exists
        yet, so the task becomes visible in Founder State and waits."""
        self._escalations += 1
        self._publish(
            EventType.TASK_ESCALATED,
            task_id=task.task_id,
            capability=task.capability,
            payload={"attempts": self._config.max_attempts},
            error=error,
        )
        self._report_failure(task, error)

    def _report_failure(
        self, task: Task, error: str, evidence_id: str | None = None
    ) -> None:
        objective_id = self._objective_of(task)
        try:
            reported = self._mc.task_failed(task.task_id, error, objective_id=objective_id)
            if evidence_id:
                reported.evidence_id = evidence_id
        except Exception as exc:  # noqa: BLE001 — reporting must never take down the loop
            self._publish(
                EventType.RUNTIME_ERROR,
                task_id=task.task_id,
                error=f"could not report failure: {exc}",
            )
        self._tasks_failed += 1

    def _recover(self) -> None:
        if self._state is RuntimeState.RECOVERING:
            self._go_idle(reason="recovered")
            return
        try:
            self._transition(RuntimeState.RECOVERING)
        except Exception:  # noqa: BLE001 — already somewhere that cannot reach RECOVERING
            return
        self._go_idle(reason="recovered")

    def _go_idle(self, reason: str) -> None:
        if self._state is RuntimeState.IDLE:
            return
        self._transition(RuntimeState.IDLE)
        self._publish(EventType.RUNTIME_IDLE, payload={"cycle": self._cycle, "reason": reason})

    # ---- health ------------------------------------------------------

    def health(self) -> RuntimeHealth:
        executives = self._mc.executives.all()
        return RuntimeHealth(
            state=self._state,
            uptime_seconds=self._uptime_seconds(),
            active_cycle=self._cycle,
            queue_length=self._queue_length(),
            executives_online=len(executives),
            executives_busy=sum(1 for e in executives if e.current_task_id is not None),
            last_dispatch_at=self._last_dispatch_at,
            last_verification_at=self._last_verification_at,
            tasks_completed=self._tasks_completed,
            tasks_failed=self._tasks_failed,
            retries_performed=self._retries_performed,
            escalations=self._escalations,
        )

    def _uptime_seconds(self) -> float:
        if self._started_at is None:
            return 0.0
        return (self._clock() - self._started_at).total_seconds()

    def _queue_length(self) -> int:
        """Everything not yet in a terminal state, across every objective
        -- read from Mission Control, never tracked separately."""
        pending = 0
        for objective in self._mc.dispatcher.objectives():
            pending += sum(
                1
                for task in objective.tasks
                if task.state not in {TaskState.COMPLETED, TaskState.FAILED}
            )
        return pending

    # ---- internals ---------------------------------------------------

    def _objective_of(self, task: Task) -> str | None:
        for objective in self._mc.dispatcher.objectives():
            if any(candidate.task_id == task.task_id for candidate in objective.tasks):
                return objective.objective_id
        return None

    def _transition(self, new_state: RuntimeState) -> None:
        if new_state is self._state:
            return
        assert_transition(self._state, new_state)
        previous = self._state
        self._state = new_state
        self._publish(
            EventType.RUNTIME_STATE_CHANGED,
            payload={"from": previous.value, "to": new_state.value, "cycle": self._cycle},
        )

    def _publish(self, event_type: EventType, **kwargs: Any) -> Event:
        event = Event(event_type=event_type, source=RUNTIME_SOURCE, **kwargs)
        self._mc.bus.publish(event)
        return event


__all__ = ["MISSION_CONTROL_SOURCE", "RUNTIME_SOURCE", "RuntimeEngine", "UnknownGateway"]
