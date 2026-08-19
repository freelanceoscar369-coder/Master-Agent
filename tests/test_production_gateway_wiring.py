"""A production Executive must not lose its verification adapter.

Two composition roots wire the same Executives:

* `launcher/boot.py` -- the CLI path
* `kalpavriksha_desktop.py` -- the Founder Edition

`boot.py` had wired the verifying `FilesystemGateway` since it was
written. The Founder Edition had not, and no production `BrowserGateway`
existed outside test support at all, so every gateway in the packaged app
was the generic `PluginGateway` -- whose `verify()` returns `None`
unconditionally. A live six-step mission produced no Evidence for any
step, completed on execution success alone, and told Onkar "Done" for a
folder that was empty.

Nothing was broken to cause that. The wiring simply drifted, silently, in
one root and not the other. These tests make that drift loud.

They deliberately do NOT require the two roots to become the same
application. They require one thing: a domain that has a real production
verification gateway may not fall back to the generic one.
"""
from __future__ import annotations

import ast
import pathlib

import pytest

REPO = pathlib.Path(__file__).resolve().parent.parent

#: Domains with a real production verification gateway, and the class that
#: provides it. A domain listed here may never be wired with the generic
#: `PluginGateway` in a composition root that wires it at all.
VERIFYING_GATEWAYS = {
    "filesystem": "FilesystemGateway",
    "browser": "BrowserGateway",
    "desktop": "DesktopGateway",
}

COMPOSITION_ROOTS = (
    "kalpavriksha_desktop.py",
    "src/master_agent/launcher/boot.py",
)


def _source(relative: str) -> str:
    return (REPO / relative).read_text(encoding="utf-8")


def _register_gateway_calls(source: str) -> list[ast.Call]:
    """Every `*.register_gateway(...)` call in a module."""
    tree = ast.parse(source)
    calls: list[ast.Call] = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "register_gateway"
        ):
            calls.append(node)
    return calls


def _gateway_class_names(call: ast.Call) -> set[str]:
    """The gateway classes constructed inside one register_gateway call."""
    names: set[str] = set()
    for node in ast.walk(call):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            names.add(node.func.id)
    return names


class TestTheProductionGatewaysExist:
    """Before asking whether a root wires them, prove they are real."""

    def test_each_verifying_gateway_is_importable(self):
        from master_agent.desktop.gateway import DesktopGateway
        from master_agent.plugins.browser_gateway import BrowserGateway
        from master_agent.plugins.filesystem_gateway import FilesystemGateway

        for gateway in (FilesystemGateway, BrowserGateway, DesktopGateway):
            assert hasattr(gateway, "invoke")
            assert hasattr(gateway, "verify")

    def test_the_generic_gateway_still_verifies_nothing(self):
        """The premise of this whole file. If `PluginGateway` ever grew a
        verification surface these tests would be guarding a problem that
        no longer exists, and should be revisited rather than kept."""
        from master_agent.runtime.gateway import PluginGateway
        from master_agent.verification.evidence import ExpectedOutcome

        gateway = PluginGateway(plugin=object())
        assert gateway.verify("anything", {}, ExpectedOutcome(description="d")) is None


class TestNoCompositionRootLosesVerification:

    @pytest.mark.parametrize("root", COMPOSITION_ROOTS)
    def test_a_verifying_domain_is_never_wired_generically(self, root):
        source = _source(root)

        for call in _register_gateway_calls(source):
            constructed = _gateway_class_names(call)
            if "PluginGateway" not in constructed:
                continue

            # This call uses the generic gateway. That is fine only if it
            # is not one of the domains that has a real one.
            rendered = ast.unparse(call)
            for domain, gateway_class in VERIFYING_GATEWAYS.items():
                assert domain not in rendered.lower(), (
                    f"{root} wires the {domain} Executive with the generic "
                    f"PluginGateway, which verifies nothing, while "
                    f"{gateway_class} exists. This is exactly the drift that "
                    f"let a packaged mission complete without Evidence."
                )

    def test_the_founder_edition_wires_every_verifying_gateway(self):
        source = _source("kalpavriksha_desktop.py")
        constructed: set[str] = set()
        for call in _register_gateway_calls(source):
            constructed |= _gateway_class_names(call)

        missing = set(VERIFYING_GATEWAYS.values()) - constructed
        assert not missing, f"Founder Edition does not wire: {sorted(missing)}"


class TestExecutionPathsArePreserved:
    """The gateways add Evidence. They must not change how anything runs."""

    def test_the_desktop_gateway_inherits_invoke_verbatim(self):
        """`DesktopGateway` overrides `verify()` and nothing else, so the
        Desktop execution path -- DesktopPlugin -> registered Action ->
        DesktopExecutor / DesktopExecutiveV2 -> Process/Window/UIA -- is
        provably untouched by this wiring."""
        from master_agent.desktop.gateway import DesktopGateway
        from master_agent.runtime.gateway import PluginGateway

        assert issubclass(DesktopGateway, PluginGateway)
        assert "invoke" not in DesktopGateway.__dict__, (
            "DesktopGateway overrides invoke -- Desktop execution is no "
            "longer provably the same path"
        )

    def test_the_browser_gateway_drives_the_existing_worker(self):
        """Verification is an adapter around the existing capability, not a
        replacement for it: `invoke()` goes through `BrowserWorker
        .run_step`, the same call the Browser Executive has always used."""
        import inspect

        from master_agent.plugins.browser_gateway import BrowserGateway

        invoke = inspect.getsource(BrowserGateway.invoke)
        assert "run_step" in invoke
        assert "self._worker" in invoke

    def test_the_filesystem_gateway_drives_the_existing_worker(self):
        import inspect

        from master_agent.plugins.filesystem_gateway import FilesystemGateway

        invoke = inspect.getsource(FilesystemGateway.invoke)
        assert "run_step" in invoke
        assert "self._worker" in invoke


class TestVerificationSupportIsStatedNotGuessed:
    """Each domain must be able to say which capabilities it can verify.
    An unsupported capability yields no Evidence -- never a fabricated
    pass, and never a fallback to the Planner's text-shaped checks."""

    def test_filesystem_queries_are_not_claimed_as_verifiable(self):
        from master_agent.plugins.filesystem_expectations import supports

        # Changing the world -- verifiable.
        for capability in ("create_folder", "write_file", "delete_folder"):
            assert supports(capability)

        # Answering a question -- not a world change. An exists-check here
        # would mark a correct `file_exists -> False` as a failure.
        for capability in ("read_file", "list_directory", "file_exists"):
            assert not supports(capability)

    def test_browser_interaction_capabilities_are_not_claimed(self):
        from master_agent.plugins.browser_expectations import subject

        for capability in ("open_browser_session", "navigate",
                           "observe_browser", "close_browser_session"):
            assert subject(capability) is not None

        for capability in ("click", "type_text", "press_key"):
            assert subject(capability) is None

    def test_desktop_input_capabilities_are_not_claimed(self):
        from master_agent.desktop.gateway import supports

        for capability in ("launch_application", "close_application",
                           "focus_window", "bring_to_front"):
            assert supports(capability)

        # No generic read-only postcondition exists for these.
        #
        # `close_window` was briefly claimed here and should not have been:
        # the payload names an application while execution resolves a
        # window handle internally, so afterwards -- without reading the
        # Action's own report -- "the intended window closed and a sibling
        # remains" cannot be told apart from "the intended window is still
        # open". See `test_desktop_verification_semantics.py`.
        for capability in ("desktop_click", "desktop_press_key",
                           "execute_command", "close_window"):
            assert not supports(capability)

    def test_an_unsupported_capability_yields_no_evidence(self):
        from master_agent.desktop.gateway import DesktopGateway
        from master_agent.verification.evidence import ExpectedOutcome

        gateway = DesktopGateway(plugin=object())
        evidence = gateway.verify(
            "desktop_click", {"target": "OK"}, ExpectedOutcome(description="clicked")
        )
        assert evidence is None, "a fabricated verdict for an unverifiable action"
