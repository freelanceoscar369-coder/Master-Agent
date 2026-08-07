"""C28 · The mission vocabulary, and the ephemeral context that carries
one mission's state.

## `DesktopTask` — what Founder Runtime sends, and what it does not

A `DesktopTask` is an ordered list of `MissionStep`s Founder Runtime has
**already decided**. Each step names one primitive tactical action
(click, type, focus, wait, execute/launch, close) and what Verify should
find true afterward. **The Operator invents no step, no target
coordinate, and no application choice** — every one of those is already
in the task when it arrives. What the Operator *does* decide, inside the
bounds of one step, is tactical: which of a step's `primary`/`alternate`
targets to click, whether to retry, whether to refocus first. See
`tactical_recovery.py` for exactly where that boundary is drawn.

## `MissionContext` — ephemeral, and provably so

*"Lives only during one execution... Destroyed immediately after
mission. Never persisted. Never enters Memory."* This is enforced
structurally, not by convention: `MissionContext` is a plain, unexported-
from-`__init__` value created **inside** `DesktopOperator.execute()`'s
own call frame, held nowhere else. `DesktopOperator` itself has no
`_context`/`_mission_context` attribute — a test
(`test_mission_context_does_not_survive_execute`) confirms the operator
instance carries no reference to any `MissionContext` after `execute()`
returns, which is the only way Python can prove "nothing kept it alive"
short of watching the garbage collector.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from master_agent.desktop.perception import ReadinessState

if TYPE_CHECKING:
    from master_agent.desktop.perception import DesktopState


class ActionKind(str, Enum):
    """The primitive tactical actions a `MissionStep` may name. Closed —
    every one maps to exactly one `DesktopExecutor` (C26) call; there is
    no seventh kind an Operator could invent."""

    CLICK = "click"
    TYPE = "type"
    FOCUS = "focus"
    WAIT = "wait"
    EXECUTE = "execute"
    CLOSE = "close"


@dataclass(frozen=True)
class StepAction:
    """One tactical action, as Founder Runtime specified it. `alternate_*`
    is the *"click A or B"* case: a second candidate target the Decide
    phase may choose instead of `x`/`y` — never a target the Operator
    invented, always one Founder Runtime already named as acceptable."""

    kind: ActionKind
    x: int | None = None
    y: int | None = None
    alternate_x: int | None = None
    alternate_y: int | None = None
    text: str | None = None
    wait_seconds: float | None = None

    def __post_init__(self) -> None:
        if self.kind is ActionKind.CLICK and (self.x is None or self.y is None):
            raise ValueError("a CLICK action requires x and y")
        if self.kind is ActionKind.TYPE and not self.text:
            raise ValueError("a TYPE action requires text")
        if self.kind is ActionKind.WAIT and not self.wait_seconds:
            raise ValueError("a WAIT action requires wait_seconds")
        if self.wait_seconds is not None and self.wait_seconds <= 0:
            raise ValueError("wait_seconds must be positive")

    @property
    def has_alternate(self) -> bool:
        return self.alternate_x is not None and self.alternate_y is not None


@dataclass(frozen=True)
class ExpectedOutcome:
    """What Verify checks, via Desktop Perception (C27) — never a
    fabricated check the Operator invented. `readiness=None` means the
    step declares no readiness expectation and Verify checks only
    `expect_change`."""

    readiness: ReadinessState | None = None
    """Checked by equality against the step's actual observed readiness
    in `state_machine.py`. `None` means the step declares no readiness
    expectation."""

    expect_change: bool = True
    """Whether the observation should differ from the previous one at
    all. `False` for a step whose success looks like *"nothing moved"*
    (e.g. a click that opens no new window by design)."""


@dataclass(frozen=True)
class MissionStep:
    """One step of a `DesktopTask`. Every field the brief's own Step
    Timeout Governor and Tactical Decision Boundary require."""

    application: str
    action: StepAction
    expected: ExpectedOutcome
    timeout_seconds: float

    def __post_init__(self) -> None:
        if not self.application or not self.application.strip():
            raise ValueError("a step must name its application")
        if self.timeout_seconds <= 0:
            raise ValueError("every step must carry a positive timeout")


@dataclass(frozen=True)
class DesktopTask:
    """Founder Runtime's entire request. One mission, already planned —
    the Operator executes it and decides nothing about its shape."""

    mission_id: str
    application: str
    steps: tuple[MissionStep, ...]

    def __post_init__(self) -> None:
        if not self.mission_id or not self.mission_id.strip():
            raise ValueError("a task must carry a mission_id")
        if not self.steps:
            raise ValueError("a task with no steps executes nothing")


@dataclass
class MissionContext:
    """Ephemeral. See the module docstring. Mutable — this is the one
    place in the whole C22–C28 lineage state is allowed to change in
    place, because nothing here is ever read by a second party: it lives
    and dies inside one `execute()` call."""

    task: DesktopTask
    started_at: datetime
    baseline_observation: DesktopState | None = None
    current_observation: DesktopState | None = None
    previous_action: StepAction | None = None
    step_retries: int = 0
    step_started_at: datetime | None = None
    verification_delta: tuple[str, ...] = field(default_factory=tuple)
    step_log: list[str] = field(default_factory=list)

    def begin_step(self, now: datetime) -> None:
        """Reset per-step bookkeeping. Called once at the start of each
        `MissionStep` — retries reset because the retry ceiling
        (`tactical_recovery.MAX_RETRIES`) is per-step, not per-mission: a
        mission of five steps that each needed one retry is not the same
        failure as one step needing five."""
        self.step_retries = 0
        self.step_started_at = now
        self.previous_action = None

    def record_observation(self, observation: DesktopState) -> None:
        if self.baseline_observation is None:
            self.baseline_observation = observation
        self.current_observation = observation

    def record_delta(self, changed_sections: tuple[str, ...]) -> None:
        self.verification_delta = changed_sections

    def record_step_result(self, line: str) -> None:
        self.step_log.append(line)
