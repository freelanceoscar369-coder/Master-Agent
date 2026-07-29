"""Worker Contract tests -- confirms every Browser Action satisfies the
exact same Action ABC (executor/action.py) every Filesystem Action already
implements, with no new or bespoke contract invented for Browser. This is
the concrete answer to Founder Review questions 3/4/10: Desktop Worker or
Terminal Worker can be built the same way, because "the way" is this
contract, unchanged.
"""
from __future__ import annotations

from master_agent.executor.action import Action
from master_agent.executor.actions.browser.click import ClickAction
from master_agent.executor.actions.browser.close_session import CloseBrowserSessionAction
from master_agent.executor.actions.browser.navigate import NavigateAction
from master_agent.executor.actions.browser.observe import ObserveBrowserAction
from master_agent.executor.actions.browser.open_session import OpenBrowserSessionAction
from master_agent.executor.actions.browser.press_key import PressKeyAction
from master_agent.executor.actions.browser.scroll import ScrollAction
from master_agent.executor.actions.browser.type_text import TypeTextAction
from master_agent.executor.actions.browser.wait_for_selector import WaitForSelectorAction
from master_agent.executor.executor import LocalExecutor
from master_agent.permissions.permission_system import PermissionSystem
from master_agent.plugins.base import PermissionCategory, RiskTier
from tests.browser_test_support import make_executor_and_sessions

ALL_BROWSER_ACTION_CLASSES = (
    OpenBrowserSessionAction,
    CloseBrowserSessionAction,
    NavigateAction,
    ClickAction,
    TypeTextAction,
    PressKeyAction,
    ScrollAction,
    WaitForSelectorAction,
    ObserveBrowserAction,
)


def test_every_browser_action_is_a_real_action_subclass():
    for action_cls in ALL_BROWSER_ACTION_CLASSES:
        assert issubclass(action_cls, Action)


def test_every_browser_action_declares_the_full_contract():
    _, sessions = make_executor_and_sessions()
    for action_cls in ALL_BROWSER_ACTION_CLASSES:
        action = action_cls(sessions)
        assert isinstance(action.name, str) and action.name
        assert isinstance(action.description, str) and action.description
        assert isinstance(action.risk_tier, RiskTier)
        assert isinstance(action.permission_category, PermissionCategory)
        assert isinstance(action.expected_result, str) and action.expected_result
        assert isinstance(action.required_parameters(), list)


def test_every_browser_action_validate_is_side_effect_free():
    """validate() must never touch a browser or perform a side effect --
    calling it with an empty payload against a completely unopened
    BrowserSessionManager must never raise, only return error strings
    (mirrors executor/action.py's Action.validate() contract)."""
    _, sessions = make_executor_and_sessions()
    for action_cls in ALL_BROWSER_ACTION_CLASSES:
        action = action_cls(sessions)
        errors = action.validate({})
        assert isinstance(errors, list)
        assert all(isinstance(e, str) for e in errors)


def test_all_nine_actions_register_on_a_shared_executor_without_name_collisions():
    executor = LocalExecutor(PermissionSystem())
    _, sessions = make_executor_and_sessions()
    for action_cls in ALL_BROWSER_ACTION_CLASSES:
        executor.register(action_cls(sessions))
    assert len(executor.log) == 0  # registering never executes or logs anything


def test_browser_actions_do_not_collide_with_filesystem_action_names():
    """Browser and Filesystem are two independent capability families --
    proving they can share one LocalExecutor/PluginRegistry without a name
    clash is part of what makes the Capability Registry pattern scale
    (KALPAVRIKSHA_VISION_V2.md §5.1)."""
    from master_agent.plugins.filesystem_plugin import _PRIMITIVE_ACTION_CLASSES as FS_ACTIONS

    fs_names = {cls(locations={}).name for cls in FS_ACTIONS}
    browser_names = set()
    _, sessions = make_executor_and_sessions()
    for action_cls in ALL_BROWSER_ACTION_CLASSES:
        browser_names.add(action_cls(sessions).name)

    assert fs_names.isdisjoint(browser_names)


def test_filesystem_and_browser_plugins_coexist_on_one_executor_and_registry():
    from master_agent.plugins.browser_plugin import BrowserPlugin
    from master_agent.plugins.filesystem_plugin import FilesystemPlugin
    from master_agent.plugins.registry import PluginRegistry

    executor = LocalExecutor(PermissionSystem())
    _, sessions = make_executor_and_sessions()
    fs_plugin = FilesystemPlugin(executor, locations={})
    browser_plugin_instance = BrowserPlugin(executor, sessions)

    registry = PluginRegistry()
    registry.register(fs_plugin)
    registry.register(browser_plugin_instance)

    assert registry.find_for_capability("create_folder")[0] is fs_plugin
    assert registry.find_for_capability("navigate")[0] is browser_plugin_instance
