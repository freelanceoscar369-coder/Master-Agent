"""The Founder path for a filesystem request, at the contract level.

Every defect covered here was found by a founder typing an ordinary
sentence into the packaged app, and each one was invisible to the suite
because nothing asserted on the *route* a request takes -- only on the
pieces in isolation. These tests need no provider: they assert the
contracts the Planner reads and the routing the Intent Layer performs.
"""
from __future__ import annotations

from master_agent.brain import IntentLayer
from master_agent.capabilities.extraction import contracts_from_actions
from master_agent.capabilities.index import build_index
from master_agent.executor.actions.create_folder import CreateFolderAction
from master_agent.executor.executor import LocalExecutor
from master_agent.mission_control.capabilities import qualified_name
from master_agent.permissions.permission_system import PermissionSystem
from master_agent.planner.catalogue import catalogue_from_index, render
from master_agent.plugins.base import RiskTier
from master_agent.plugins.filesystem_plugin import FilesystemPlugin


def _create_folder_option():
    plugin = FilesystemPlugin(LocalExecutor(PermissionSystem()))
    contracts = contracts_from_actions(
        plugin._actions, plugin.manifest.name, qualified_name
    )
    index = build_index(contracts, loader={c.canonical_id: c for c in contracts}.get)
    return next(
        o for o in catalogue_from_index(index) if o.name == "Filesystem.CreateFolder"
    )


class TestIncompleteFolderRequestsAreClarified:
    """A missing parameter is a question, never a guess.

    `_patterns` is first-match-wins and only listed "create a folder
    called". "Create a folder" -- precisely the case that needs
    clarifying, because no name was given -- therefore fell through to the
    generic ("create", CreateProjectIntent) catch-all and asked the
    founder "What should the *project* be called?" about a folder.
    """

    def test_a_bare_folder_request_asks_about_a_folder(self):
        result = IntentLayer().parse("Create a folder")
        assert result.needs_clarification
        assert "folder" in result.clarification.question.lower()
        assert "project" not in result.clarification.question.lower()

    def test_a_location_without_a_name_still_asks_for_the_name(self):
        """The location is known; the name is not. Nothing may be invented
        from it -- and no folder called "Desktop" may appear."""
        result = IntentLayer().parse("Create a folder on my Desktop")
        assert result.needs_clarification
        assert "folder" in result.clarification.question.lower()

    def test_other_phrasings_route_to_the_folder_parser(self):
        for text in ("create folder", "Make a folder", "Create a new folder"):
            result = IntentLayer().parse(text)
            assert result.needs_clarification, text
            assert "folder" in result.clarification.question.lower(), text

    def test_project_requests_are_untouched(self):
        """The folder patterns sit above the catch-all; they must not
        swallow project requests on the way past."""
        result = IntentLayer().parse("Create a project")
        assert result.needs_clarification
        assert "project" in result.clarification.question.lower()

    def test_a_complete_request_is_not_clarified(self):
        """Complete now means BOTH founder-owned fields: what it is called
        and where it goes. A name alone is no longer a complete request --
        see `test_create_folder_intent_completeness.py`."""
        result = IntentLayer().parse("Create a folder called Research on Desktop")
        assert not result.needs_clarification
        assert result.intent is not None


class TestCreateFolderPublishesItsWholeContract:
    """The Planner can only fill an argument it has been told exists."""

    def test_name_is_required_and_location_is_optional(self):
        action = CreateFolderAction()
        assert action.required_parameters() == ["name"]
        optional = {o["name"]: o for o in action.optional_parameters()}
        assert "location" in optional

    def test_the_default_location_is_the_actions_own_long_standing_one(self):
        """Stated, not invented: `run()`/`validate()` have always fallen
        back to "desktop"."""
        optional = {o["name"]: o for o in CreateFolderAction().optional_parameters()}
        assert optional["location"]["default"] == "desktop"

    def test_the_contract_is_closed(self):
        """`args_complete` is what lets the Planner trust the argument
        list is the whole story rather than a floor."""
        assert _create_folder_option().args_complete is True

    def test_the_planner_sees_both_arguments(self):
        option = _create_folder_option()
        assert option.required_args == ("name",)
        assert "location" in option.optional_args

    def test_the_rendered_prompt_line_separates_name_from_location(self):
        """Only argument NAMES are rendered, so the split has to survive
        into the description or the model never learns it. Asked to
        "create a folder called Research on my Desktop" without this, the
        Planner passed name="Research on my Desktop"."""
        line = render([_create_folder_option()])
        assert "optional: location" in line
        assert "'location'" in line
        assert "'name'" in line

    def test_the_risk_tier_is_reversible(self):
        """A raw shell fallback reclassified this as irreversible and
        forced a founder approval the real policy never asked for."""
        assert CreateFolderAction.risk_tier is RiskTier.REVERSIBLE_WRITE
        assert _create_folder_option().risk_tier == "reversible_write"


class TestFounderEditionRegistersFilesystem:
    """The typed action existed all along; Founder Edition never
    registered the plugin that exposes it, so the Planner could not see
    `create_folder` and satisfied "create a folder" with
    `desktop.execute_command` -- a raw shell string."""

    def test_the_composition_root_registers_the_filesystem_plugin(self):
        import inspect

        import kalpavriksha_desktop as root

        source = inspect.getsource(root._build_mission_pipeline)
        assert "FilesystemPlugin" in source
        assert "registry.register(filesystem_plugin)" in source

    def test_it_is_wired_through_every_seam_the_runtime_needs(self):
        """Gateway, pre-grant loop and planner catalogue -- not just the
        registry.

        The gateway half was `assert "register_gateway(filesystem_plugin"
        in source`, which asserted a source SPELLING rather than the
        wiring. It broke the moment the call was reformatted across lines
        to pass a verifying `FilesystemGateway` -- i.e. it failed on a
        change that made the wiring strictly better. Read over the parsed
        AST instead, so the property under test is "filesystem is
        registered, with something that verifies".
        """
        import ast
        import inspect

        import kalpavriksha_desktop as root

        source = inspect.getsource(root._build_mission_pipeline)

        registered: list[str] = []
        for node in ast.walk(ast.parse(source.lstrip())):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "register_gateway"
            ):
                registered.append(ast.unparse(node))

        filesystem_wiring = [call for call in registered if "filesystem_plugin" in call]
        assert filesystem_wiring, "the filesystem Executive has no gateway"
        assert any("FilesystemGateway" in call for call in filesystem_wiring), (
            "the filesystem Executive is wired with a gateway that cannot "
            "verify; a step would complete on execution success alone"
        )

        assert source.count("browser_plugin, desktop_plugin, filesystem_plugin") >= 2
