"""The Desktop Executive (Mission Brief 030).

Kalpavriksha's eyes and hands over the local machine: what software
exists, what version, what is running, and — with founder approval — start
it, open something with it, or stop it.

**It executes. It does not decide.** It has no idea what a model is,
cannot compare two installed things, and never recommends. It reports
facts and performs the actions it is dispatched. The AI Capability Broker
(MB027, ADR-0017) will consume these facts to make choices; keeping those
two jobs apart is the whole point of MB030's Rules 1, 2, and 11, and
`tests/test_desktop_executive.py` asserts it by parsing this package for
forbidden vocabulary.

Registered exactly like every other Executive: actions on the existing
`LocalExecutor`, capabilities from the manifest, discovered by Mission
Control's existing adapter. **No architecture changed** to add it.
"""
from __future__ import annotations

from typing import Any

from master_agent.desktop.actions import DESKTOP_ACTION_CLASSES, DesktopContext
from master_agent.desktop.inventory import MachineInventory
from master_agent.desktop.probe import RealSystemProbe, SystemProbe
from master_agent.executor.action import Action
from master_agent.executor.executor import LocalExecutor
from master_agent.permissions.permission_system import GrantScope
from master_agent.plugins.base import (
    CapabilityManifest,
    InvocationResult,
    Plugin,
    PluginManifest,
)

DESKTOP_EXECUTIVE_ID = "desktop"
DESKTOP_VERSION = "1.0.0"

#: Desktop Executive Foundation 1.0. `desktop/actions.py` itself is
#: unmodified (its own module docstring says so) — these three names were
#: deliberate refusals there ("window focus needs desktop interaction,
#: which MB030 deliberately excludes... a later Desktop Interaction brief
#: owns this"). This is that brief's registration point: the verified
#: implementations in `actions_interaction.py` are registered under the
#: same capability names instead, so the Planner's catalogue shape is
#: unchanged and only what runs underneath it becomes real.
_SUPERSEDED_BY_INTERACTION_LAYER = frozenset(
    {"launch_application", "focus_window", "bring_to_front"}
)


def _default_action_classes() -> tuple[type[Action], ...]:
    # Imported here, not at module level: `actions_interaction` pulls in
    # `execution/executor.py` → `operations` → `environment_intelligence`,
    # and `environment_intelligence.derive` itself imports
    # `desktop.catalog` — a module-level import here would make importing
    # *any* `master_agent.desktop.*` submodule (via this package's own
    # `__init__.py`) execute that whole chain, circularly, before
    # `environment_intelligence` finishes initializing. Deferred to call
    # time (`DesktopPlugin.__init__`, well after both packages are fully
    # loaded), this import is safe.
    from master_agent.desktop.actions_interaction import DESKTOP_INTERACTION_ACTION_CLASSES

    base = tuple(
        cls for cls in DESKTOP_ACTION_CLASSES
        if cls.name not in _SUPERSEDED_BY_INTERACTION_LAYER
    )
    return base + DESKTOP_INTERACTION_ACTION_CLASSES


class DesktopPlugin(Plugin):
    """Exposes every Desktop action as a same-named capability.

    Mirrors `FilesystemPlugin` deliberately, down to the ADR-0005 relay:
    an Executive that is *almost* like the others is harder to reason
    about than one that is exactly like them.
    """

    def __init__(
        self,
        executor: LocalExecutor,
        probe: SystemProbe | None = None,
        action_classes: tuple[type[Action], ...] | None = None,
    ) -> None:
        self._executor = executor
        self._context = DesktopContext(probe or RealSystemProbe())
        self._actions: dict[str, Action] = {}

        for action_cls in (action_classes or _default_action_classes()):
            self._register(action_cls(self._context))

    def _register(self, action: Action) -> None:
        self._actions[action.name] = action
        self._executor.register(action)

    # ---- the Plugin contract -----------------------------------------

    @property
    def manifest(self) -> PluginManifest:
        return PluginManifest(
            name=DESKTOP_EXECUTIVE_ID,
            version=DESKTOP_VERSION,
            capabilities=[
                CapabilityManifest(
                    name=action.name,
                    description=action.description,
                    risk_tier=action.risk_tier,
                    permission_category=action.permission_category,
                )
                for action in self._actions.values()
            ],
        )

    def invoke(self, capability: str, payload: dict[str, Any]) -> InvocationResult:
        if capability not in self._actions:
            return InvocationResult(
                success=False, error=f"unsupported capability: {capability}"
            )

        # ADR-0005 relay, identical to FilesystemPlugin's: carry the
        # already-obtained approval down to the Executor's own grant key.
        # Since MB028.0 the approval that authorises this call is checked
        # at the Runtime's boundary before invoke() is ever reached.
        self._executor.permissions.grant(
            self._executor.name, capability, GrantScope.ONCE
        )
        result = self._executor.execute(capability, payload)

        if not result.success:
            return InvocationResult(
                success=False,
                error="; ".join(result.errors) or "unknown executor failure",
                execution_time_seconds=result.execution_time_seconds,
            )
        return InvocationResult(
            success=True,
            output=result.output,
            execution_time_seconds=result.execution_time_seconds,
        )

    # ---- read-only surface -------------------------------------------

    def inventory(self, refresh: bool = False) -> MachineInventory:
        """The last machine inventory, for a *reader*.

        This is how the Dashboard gets Machine Readiness without invoking
        anything (MB030 Deliverable 4/9, ADR-0016's read-only rule). It is
        a published read, in the same spirit as MIT-001's
        `PluginRegistry.all_plugins()` — reading a contract, not executing
        a capability.

        `refresh=False` by default *because the Dashboard calls it*: a
        render must never trigger a machine scan, or looking at the screen
        would change what the screen reports.
        """
        if refresh:
            return self._context.refresh()
        return self._context.inventory()

    @property
    def cached_inventory(self) -> MachineInventory | None:
        """Whatever was last discovered, or None if nothing has been.
        Never scans — a caller that wants a scan asks Mission Control to
        dispatch one."""
        return self._context.cached
