"""What a Desktop Action publishes must be what it actually reads.

`Action.optional_parameters()` has deliberate semantics:

    None          the optional roster has NOT been declared
    []            this Action truthfully accepts NO optional arguments
    [descriptors] these are ALL the optional arguments it accepts

A non-None return closes the input schema and sets `args_complete=True`,
and the deterministic planner refuses any capability whose roster is open
-- correctly, because an open roster means "optional arguments exist and
are not listed", and guessing at them is exactly what that planner exists
to prevent. Fifteen of nineteen Desktop capabilities were open, so a
founder who spelled a Desktop request out in full still could not have it
planned without a model.

Closing a schema is therefore a claim, and this is the guard on it. It
reads each Action's own `validate()`, `run()` and every helper they call,
collects the payload keys the implementation actually consumes, and holds
that against what the Action publishes. A future Action that starts
reading `parameters.get("new_option")` while still publishing a closed
roster fails here rather than silently advertising a contract it does not
honour.
"""
from __future__ import annotations

import ast
import inspect
import textwrap

import pytest

from master_agent.desktop.actions import DesktopContext
from master_agent.desktop.plugin import DesktopPlugin
from master_agent.executor.executor import LocalExecutor
from master_agent.permissions.permission_system import PermissionSystem

#: Read on `parameters`/`payload` but never a founder-supplied argument --
#: a helper's own local, or a key this Action inherits without ever
#: calling the helper that reads it. Each entry needs a reason, so the set
#: cannot quietly become a way to hide a real input.
NOT_AN_INPUT: dict[str, set[str]] = {
    # `_DesktopAction._require_known_application()` reads "application",
    # and every Action that CALLS it already requires that argument. These
    # inherit the helper without calling it.
    "ExecuteCommandAction": {"application"},
    "ListInstalledSoftwareAction": {"application"},
    "ListRunningProcessesAction": {"application"},
    "OpenFileAction": {"application"},
    "OpenFolderAction": {"application"},
}


def actions():
    plugin = DesktopPlugin(
        LocalExecutor(PermissionSystem()), DesktopContext(probe=None)
    )
    return sorted(plugin._actions.items())


def consumed_keys(action) -> set[str]:
    """Every literal payload key this Action's implementation reads,
    across its whole MRO -- `validate()`, `run()` and any helper."""
    found: set[str] = set()
    for klass in type(action).__mro__:
        for member in vars(klass).values():
            if not inspect.isfunction(member):
                continue
            try:
                tree = ast.parse(textwrap.dedent(inspect.getsource(member)))
            except (OSError, SyntaxError):  # pragma: no cover - defensive
                continue
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "get"
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id in ("parameters", "payload")
                    and node.args
                    and isinstance(node.args[0], ast.Constant)
                ):
                    found.add(node.args[0].value)
                if (
                    isinstance(node, ast.Subscript)
                    and isinstance(node.value, ast.Name)
                    and node.value.id in ("parameters", "payload")
                    and isinstance(node.slice, ast.Constant)
                ):
                    found.add(node.slice.value)
    return found


@pytest.mark.parametrize("name,action", actions())
def test_a_closed_schema_publishes_every_input_it_reads(name, action):
    """The parity claim. Required + declared optional must cover every
    key the implementation consumes."""
    optional = action.optional_parameters()
    if optional is None:
        pytest.skip(f"{name} does not claim a complete roster")

    published = set(action.required_parameters()) | {o["name"] for o in optional}
    ignorable = NOT_AN_INPUT.get(type(action).__name__, set())
    unpublished = consumed_keys(action) - published - ignorable

    assert not unpublished, (
        f"{name} reads {sorted(unpublished)} but publishes a CLOSED roster "
        f"of {sorted(published)} -- either declare them or return None"
    )


@pytest.mark.parametrize("name,action", actions())
def test_nothing_published_is_absent_from_the_implementation(name, action):
    """The other direction: a declared argument nobody reads is an
    advertisement for behaviour that does not exist."""
    optional = action.optional_parameters()
    if optional is None:
        pytest.skip(f"{name} does not claim a complete roster")

    consumed = consumed_keys(action)
    for descriptor in optional:
        assert descriptor["name"] in consumed, (
            f"{name} advertises optional {descriptor['name']!r}, which its "
            f"implementation never reads"
        )


@pytest.mark.parametrize("name,action", actions())
def test_every_descriptor_is_shaped_like_a_contract(name, action):
    optional = action.optional_parameters()
    if not optional:
        return
    for descriptor in optional:
        assert set(descriptor) <= {"name", "type", "description", "default"}
        assert descriptor.get("name")
        assert descriptor.get("description"), (
            f"{name}: {descriptor.get('name')} has no description for a planner to read"
        )


def test_the_desktop_estate_declares_its_input_contracts():
    """Fifteen of nineteen were open. This records where that landed, and
    fails if a future Action reopens one without saying why."""
    open_rosters = [
        name for name, action in actions() if action.optional_parameters() is None
    ]

    assert open_rosters == [], (
        f"these Desktop capabilities no longer publish a complete input "
        f"roster: {open_rosters}"
    )


# ═══════════ what the Planner is handed, and what it may send ═══════════

from master_agent.capabilities.extraction import contracts_from_actions  # noqa: E402
from master_agent.mission_control.capabilities import qualified_name  # noqa: E402


def contracts():
    plugin = DesktopPlugin(
        LocalExecutor(PermissionSystem()), DesktopContext(probe=None)
    )
    built = contracts_from_actions(plugin._actions, plugin.manifest.name, qualified_name)
    return {c.canonical_id: c for c in built}


class TestThePlannerSeesTheRealSignature:
    """Five shapes, chosen to cover what a Desktop request can look like.
    No destructive operation is executed anywhere here -- this is metadata
    and payload validation, and running a real close or delete to prove a
    contract would be absurd."""

    def test_A_required_only(self):
        contract = contracts()["Desktop.IsInstalled"]

        assert contract.inputs.required_names == ("application",)
        assert contract.inputs.known and contract.inputs.closed
        assert contract.accepts({"application": "chrome"}) == ()

    def test_B_required_plus_optional(self):
        contract = contracts()["Desktop.ReadText"]

        assert contract.inputs.required_names == ("application",)
        optional = set(contract.inputs.field_names) - {"application"}
        assert optional == {"control_class", "target_name_contains"}
        assert contract.accepts(
            {"application": "notepad", "control_class": "Edit"}
        ) == ()

    def test_C_no_input_at_all(self):
        """`list_installed_software` requires nothing. A closed roster is
        what tells the Planner that is the whole truth rather than an
        unfinished contract."""
        contract = contracts()["Desktop.ListInstalledSoftware"]

        assert contract.inputs.required_names == ()
        assert contract.inputs.closed
        assert contract.accepts({}) == ()

    def test_D_a_boolean_optional(self):
        contract = contracts()["Desktop.ListRunningProcesses"]

        assert "owned_only" in contract.inputs.field_names
        assert contract.accepts({"owned_only": True}) == ()
        assert contract.accepts({}) == ()

    def test_E_an_interaction_capability(self):
        contract = contracts()["Desktop.DesktopClick"]

        assert contract.inputs.required_names == ("application", "x", "y")
        assert contract.inputs.closed
        assert contract.accepts({"application": "notepad", "x": 10, "y": 20}) == ()

    def test_an_unknown_argument_is_rejected_by_a_closed_schema(self):
        """The point of closing the roster. Before this, an argument the
        contract never published could be passed with nothing to catch
        it."""
        contract = contracts()["Desktop.IsInstalled"]

        problems = contract.accepts(
            {"application": "chrome", "not_a_real_argument": 1}
        )

        assert problems, "a closed schema accepted an argument it never published"
        assert any("not_a_real_argument" in p for p in problems)

    def test_a_missing_required_argument_is_still_rejected(self):
        contract = contracts()["Desktop.DesktopClick"]

        problems = contract.accepts({"application": "notepad"})

        assert problems
