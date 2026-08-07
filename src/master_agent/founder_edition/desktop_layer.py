"""C30 · The desktop layer, composed once and held once.

```
   C25 DesktopExecutiveV2   ── authored operational knowledge
        │
        ▼
   C26 DesktopExecutor      ── the one door that can act
        │
        ├──────────────────► C28 DesktopOperator  (holds both, adds the loop)
        │                          ▲
   C27 DesktopObserver ────────────┘
        (the one door that reads)
```

**Four objects, one of each, constructed once.** This module's entire
reason to exist is the brief's own test: *"No duplicated initialization.
No duplicated state."* `DesktopOperator()` constructs its own
`DesktopExecutor` and `DesktopObserver` when it is handed neither — so a
composition that built an executor, built an observer, and *then* built an
operator would quietly own **two** of each, and the observation history
the founder's dashboard reads would not be the history the operator's own
Verify step writes into. `DesktopLayer` builds the executor and the
observer first and hands both to the operator, so there is exactly one of
each in the process and every reader sees what every writer wrote.

## What this module does not do

It derives nothing, decides nothing, and starts nothing. It has no method
that runs a mission, and that is deliberate rather than incomplete:

> *"nothing the founder does on this surface can start work"* — C23,
> `founder_runtime/wiring.py`

Nothing in C1–C29 turns founder speech into a `DesktopTask`. Producing one
would be planning, which C29 states Somesh never does and which this brief
places outside its own scope (*"No Mission OS"*). So the Operator is
**wired and idle**: constructed, holding the one executor and the one
observer, reachable as `DesktopLayer.operator` for whatever eventually
plans a mission — and reachable through no founder-facing door here.

## Readiness is C27's observation, not a second opinion

`readiness()` calls `DesktopObserver.observe()` once and hands back its own
`as_dict()`. It re-derives no confidence, no readiness state and no
failure — those are C27's, and `Engineering/HEALTH_C27.md` already records
what each one means. The one choice this module makes is **which**
applications to ask about, and it is a fact rather than a policy: the
applications the machine inventory already reports as *installed and
currently running*. A curated watch-list would be this layer deciding what
matters to a founder, which is the invention every component from C19
onward exists to avoid.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from master_agent.desktop.execution.executor import DesktopExecutor
from master_agent.desktop.inventory import MachineInventory
from master_agent.desktop.operations import DesktopExecutiveV2
from master_agent.desktop.perception import DesktopObserver
from master_agent.desktop_operator import DesktopOperator

#: What `readiness()` reports when no machine inventory was scanned. C24's
#: own discipline: absence is stated in the words of whatever was missing,
#: never rendered as an empty-but-healthy reading.
NO_INVENTORY = (
    "no machine inventory was scanned, so nothing is known about which "
    "applications are installed or running"
)


class DesktopLayer:
    """One of each of C25, C26, C27 and C28 — never two.

    Every argument is required and every one is the object some earlier
    boot step already built. This class constructs none of them itself,
    so there is exactly one construction site for each, and it is the
    boot sequence.
    """

    __slots__ = ("_executive", "_executor", "_inventory", "_observer", "_operator")

    def __init__(
        self,
        *,
        executive: DesktopExecutiveV2,
        executor: DesktopExecutor,
        observer: DesktopObserver,
        operator: DesktopOperator,
        inventory: MachineInventory | None = None,
    ) -> None:
        if not isinstance(executive, DesktopExecutiveV2):
            raise TypeError("executive must be the DesktopExecutiveV2 this boot built")
        if not isinstance(executor, DesktopExecutor):
            raise TypeError("executor must be the DesktopExecutor this boot built")
        if not isinstance(observer, DesktopObserver):
            raise TypeError("observer must be the DesktopObserver this boot built")
        if not isinstance(operator, DesktopOperator):
            raise TypeError("operator must be the DesktopOperator this boot built")
        if inventory is not None and not isinstance(inventory, MachineInventory):
            raise TypeError("inventory must be the MachineInventory discover() returned")

        self._executive = executive
        self._executor = executor
        self._observer = observer
        self._operator = operator
        self._inventory = inventory

    # ---- the four, each reachable by name -------------------------------

    @property
    def executive(self) -> DesktopExecutiveV2:
        """C25 — authored operational knowledge. Read-only by its own
        contract; it holds no probe and performs no scan."""
        return self._executive

    @property
    def executor(self) -> DesktopExecutor:
        """C26 — the one door that can act on the desktop. Held, never
        driven from here."""
        return self._executor

    @property
    def observer(self) -> DesktopObserver:
        """C27 — the one door that reads the desktop, and the one
        observation history in this process."""
        return self._observer

    @property
    def operator(self) -> DesktopOperator:
        """C28 — wired and idle. See the module docstring for why nothing
        here hands it a mission."""
        return self._operator

    @property
    def inventory(self) -> MachineInventory | None:
        """The scan the boot sequence already performed. Never re-scanned
        — this layer holds no probe and calls `discover()` nowhere."""
        return self._inventory

    # ---- what a founder surface reads -----------------------------------

    def running_applications(self) -> tuple[str, ...]:
        """Which known applications are installed *and* currently running.

        A fact the inventory already published, transcribed. Not a
        watch-list, not a recommendation, and not sorted by importance —
        inventory order, so two reads of one inventory agree.
        """
        if self._inventory is None:
            return ()
        return tuple(
            application.key
            for application in self._inventory.installed()
            if self._inventory.running(application.key)
        )

    def readiness(self, moment: datetime) -> dict[str, Any]:
        """One C27 observation, plus the inventory facts it was taken
        against. JSON-ready, and nothing in it is re-derived.

        `moment` is a parameter for the same reason every other moment in
        this codebase is: `foundation/clock.py` forbids ambient wall-clock
        time anywhere in the decision path, and a readiness reading that
        stamped itself could not be pinned by a test.
        """
        if moment.tzinfo is None:
            raise ValueError("moment must be timezone-aware")

        watched = self.running_applications()
        state = self._observer.observe(
            moment, applications=watched, inventory=self._inventory
        )
        return {
            "observation": state.as_dict(),
            "watching": list(watched),
            "installed_count": (
                len(self._inventory.installed()) if self._inventory is not None else None
            ),
            "inventory_absent_reason": (
                None if self._inventory is not None else NO_INVENTORY
            ),
            "layers": [
                {"name": "desktop_executive", "component": "C25", "wired": True},
                {"name": "desktop_execution", "component": "C26", "wired": True},
                {"name": "desktop_perception", "component": "C27", "wired": True},
                {"name": "desktop_operator", "component": "C28", "wired": True},
            ],
        }
