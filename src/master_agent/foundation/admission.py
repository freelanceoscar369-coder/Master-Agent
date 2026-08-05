"""Admission Record — the Objective Engine's published statement that an objective is live.

Objective Engine Specification §10.2 — what crosses the boundary between
the Objective Engine and the Kernel:

```
  admit(objective)
      │
      └──► ADMISSION RECORD ──────────────────► read by K1 on every mint
             objective_id                          "does this resolve to an
             state                                  admitted, non-terminal
             consequence_ceiling                    objective?"
             budget · deadline
             required_authority                  envelope bounds every warrant
             approval_ref                        minted under this objective
```

## Why this is a value and not the Objective

§10.1: *"The Objective Engine's responsibility ends at admission. It never
calls `authorize()`."* This record is the whole of what the Kernel sees.
The Objective itself — its statement in the founder's words, its criteria,
its plan, its lineage — stays inside the Engine.

Extracting it as its own value is what lets the Kernel read K1's anchor
**without importing the Objective Engine**, which is the dependency
direction §3.6 requires and the reason C15 can ship before C17.

## The state vocabulary

`ObjectiveState` is the constitutional vocabulary ratified in **ADR-0021**.
It is **permanently separate** from Constitution §17's frozen
`Mission State`, which this module neither imports nor references. Two
distinct vocabularies, neither defined in terms of the other.

Six values, three terminal:

```
    WAITING · READY · EXECUTING          non-terminal
    COMPLETED · FAILED · SUPERSEDED      terminal
```

There is no `DRAFT`: per ADR-0021 D4 an objective that has not been
admitted publishes no record at all, and K1 already refuses an unknown
objective (Kernel Specification §7.2).

## Only `EXECUTING` permits minting

ADR-0021 D5 preserves §10.3 as written — *"`state` | K1's liveness gate |
Non-`EXECUTING` ⇒ no mints"* — and §10.2's *"K1 keeps refusing while the
objective is not `EXECUTING`."*

So `READY` and `WAITING` are non-terminal and still refuse mints. That is
not a contradiction: an objective can be perfectly alive and correctly
doing nothing (§8.1 — *"waiting must not look like failure"*).

`is_executing` and `is_terminal` are therefore **different questions**, and
both are exposed because K1 asks both.

Both are named for the **fact** they report, never for the permission they
might be read as granting. This record permits nothing; §10.3's rule that
a non-`EXECUTING` objective mints nothing is the Kernel's to apply.

## The envelope is complete or it does not exist

§10.3: *"`budget` · `deadline` · `consequence_ceiling` | The execution
contract — the envelope | **Kernel refuses a warrant exceeding any of the
three**."*

All three are required here. A record publishing two of them would
describe an envelope with one side missing, and the Kernel would enforce a
ceiling it could not see. §10.4 states the posture: the ceiling is *"where
the founder says how far this is allowed to go, once, in advance, in
calm"* — an absent ceiling is not calm, it is unbounded.

## What this record deliberately does not carry

§5.2's deliberately-absent list applies with full force — no
`progress_percent`, no `priority`, no `assignee`, no counts, no
`status_note`. *"The absences are as load-bearing as the fields."*

Beyond those, this record carries none of the Objective's own internals:
no `statement`, no `criteria`, no `plan_ref`, no `waiting` record, no
lineage. Each belongs to the Engine, and a Kernel that could read them
would be a Kernel that could second-guess admission.

## Dependencies

`ReversibilityClass` from C4 — the shipped vocabulary for the consequence
ceiling, reused rather than restated. Nothing else. No clock: `deadline`
is supplied by the caller, as everywhere else in `foundation/`.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from master_agent.foundation.warrant import ReversibilityClass


class ObjectiveState(str, Enum):
    """The published lifecycle state of an admitted objective. **ADR-0021.**

    A constitutional vocabulary, not business logic. It is what the
    Objective Engine publishes and the Kernel reads — not the Engine's
    internal bookkeeping, which may be richer (ADR-0021 D4).

    **Distinct from `Mission State`** (Constitution §5.3, §17), which is
    frozen and unmodified. Neither vocabulary is defined in terms of the
    other, and this module imports nothing from `mission_manager`.

    The vocabulary is closed at six. A seventh state is a change to what an
    objective can constitutionally be, which is a founder decision rather
    than a code change — ADR-0021 O1 records the one such question that
    remains open.
    """

    #: Admitted; nothing is running, and that is correct. §8.2's four kinds
    #: of wait all publish this.
    WAITING = "waiting"

    #: Admitted, envelope set, authority resolved — not yet executing.
    READY = "ready"

    #: Work is happening. **The only state that permits minting** (§10.3).
    EXECUTING = "executing"

    #: Every criterion verified (§3.8). Terminal.
    COMPLETED = "completed"

    #: A criterion cannot be met, established rather than assumed (§3.8).
    #: Terminal.
    FAILED = "failed"

    #: Replaced by a revised version; **the original is retained** (§3.8,
    #: §4.4). Terminal, and absolute — ADR-0021 D3: an objective never
    #: transitions out of it, and replacing one creates a new objective
    #: rather than mutating the old.
    SUPERSEDED = "superseded"

    @property
    def is_terminal(self) -> bool:
        """Whether K1 must refuse for having no live objective.

        Kernel Specification §7.2 K1 refuses an *"objective already
        completed, failed, or cancelled"*; ADR-0021 A2 restates that
        enumeration as this partition, which is what the Kernel actually
        tests.
        """
        return self in _TERMINAL

    @property
    def is_executing(self) -> bool:
        """Whether K1's liveness gate is open.

        §10.3 — *"Non-`EXECUTING` ⇒ no mints."* Deliberately **not** the
        inverse of `is_terminal`: `READY` and `WAITING` are alive and still
        mint nothing.
        """
        return self is ObjectiveState.EXECUTING


_TERMINAL = frozenset(
    {
        ObjectiveState.COMPLETED,
        ObjectiveState.FAILED,
        ObjectiveState.SUPERSEDED,
    }
)


class InvalidAdmissionRecord(ValueError):
    """Raised at construction for a record the Kernel could not rely on.

    At construction, never at read time. K1 reads this record on **every
    mint** and treats it as settled fact, so one that should not exist must
    not be constructible.
    """


@dataclass(frozen=True)
class AdmissionRecord:
    """One objective's published admission. Immutable and hashable.

    Two records with identical fields are the same admission. The record is
    never edited: §5.1 marks the envelope fields immutable, and §10.4 is
    explicit that raising the ceiling *"requires a new founder approval,
    never a re-derivation."*
    """

    #: The Kernel's K1 anchor. Opaque here — this value never resolves it.
    objective_id: str

    #: ADR-0021's published vocabulary.
    state: ObjectiveState

    #: **The highest consequence class any warrant under this objective may
    #: carry** (§10.4). Shares C4's vocabulary, so there is one ordering of
    #: consequence in the system rather than two.
    consequence_ceiling: ReversibilityClass

    #: The spend ceiling. Exact, never a float — a total that drifts is a
    #: total the founder cannot rely on. The time half of the envelope is
    #: `deadline`.
    budget: Decimal

    #: When the envelope closes. Timezone-aware, normalised to UTC.
    deadline: datetime

    #: The grant or rule this objective runs under, **resolved once at
    #: admission** and relayed downward (§10.3) — never re-asked per step.
    required_authority: str

    #: The single founder approval this objective runs under (§5.1).
    approval_ref: str

    def __post_init__(self) -> None:
        for name in ("objective_id", "required_authority", "approval_ref"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise InvalidAdmissionRecord(
                    f"{name} must be a non-empty identifier"
                )

        if not isinstance(self.state, ObjectiveState):
            raise InvalidAdmissionRecord(
                "state must be an ObjectiveState; the Mission state machine "
                "is a separate vocabulary and is not accepted here (ADR-0021)"
            )

        if not isinstance(self.consequence_ceiling, ReversibilityClass):
            raise InvalidAdmissionRecord(
                "consequence_ceiling must be a ReversibilityClass"
            )

        self._validate_budget()
        self._validate_deadline()

    def _validate_budget(self) -> None:
        if isinstance(self.budget, bool) or not isinstance(self.budget, Decimal):
            raise InvalidAdmissionRecord(
                "budget must be a Decimal; binary floats cannot represent a "
                "currency exactly and a ceiling that drifts is not a ceiling"
            )
        if self.budget < 0:
            raise InvalidAdmissionRecord(
                "budget must not be negative; an envelope cannot authorise "
                "less than nothing"
            )

    def _validate_deadline(self) -> None:
        if not isinstance(self.deadline, datetime):
            raise InvalidAdmissionRecord("deadline must be a datetime")
        if self.deadline.tzinfo is None:
            raise InvalidAdmissionRecord(
                "deadline must be timezone-aware; every moment in "
                "Kalpavriksha comes from the canonical clock and is aware"
            )
        object.__setattr__(self, "deadline", self.deadline.astimezone(UTC))

    # ---- reading ------------------------------------------------------

    @property
    def is_terminal(self) -> bool:
        """Whether the objective has ended. K1 refuses against this."""
        return self.state.is_terminal

    @property
    def is_executing(self) -> bool:
        """Whether K1's liveness gate is open for this objective.

        A fact, not a decision. K1 combines it with the checks §7.2 assigns
        the Kernel; this record neither performs nor anticipates them.
        """
        return self.state.is_executing

    def as_dict(self) -> dict[str, Any]:
        """A deterministic, JSON-ready projection.

        Fixed key order. `budget` renders as a string so no precision is
        lost crossing JSON, where every number is a float — the convention
        `Cost.as_dict()` established. ISO-8601 UTC deadline.
        """
        return {
            "objective_id": self.objective_id,
            "state": self.state.value,
            "consequence_ceiling": self.consequence_ceiling.value,
            "budget": str(self.budget),
            "deadline": self.deadline.isoformat(),
            "required_authority": self.required_authority,
            "approval_ref": self.approval_ref,
        }
