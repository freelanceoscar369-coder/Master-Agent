"""MB039 Stages A2–A4 — index, extraction, and the Planner using them.

The defect under repair, stated once: MB037's first live plan named the
right two capabilities and got **both payloads wrong**, because the only
thing published about an argument was an English sentence.
"""
from __future__ import annotations

import pytest

from master_agent.capabilities.contract import (
    IRREVERSIBLE,
    NO_EFFECT,
    REVERSIBLE,
    UNKNOWN,
    CapabilityContract,
    Schema,
    Version,
)
from master_agent.capabilities.extraction import (
    SOURCE_ACTION,
    contract_from_action,
    contracts_from_actions,
)
from master_agent.capabilities.index import (
    IndexEntry,
    build_index,
    entry_for,
)
from master_agent.executor.executor import LocalExecutor
from master_agent.mission_control.capabilities import qualified_name
from master_agent.permissions.permission_system import PermissionSystem
from master_agent.planner.catalogue import catalogue_from_index, render, signature
from master_agent.planner.parsing import validate
from master_agent.planner.plan import BAD_PAYLOAD
from master_agent.plugins.filesystem_plugin import FilesystemPlugin
from tests.planner_test_support import document, step, success


def filesystem_actions() -> dict:
    return FilesystemPlugin(LocalExecutor(PermissionSystem()))._actions


def filesystem_contracts() -> tuple[CapabilityContract, ...]:
    return contracts_from_actions(filesystem_actions(), "filesystem", qualified_name)


def contract_named(suffix: str) -> CapabilityContract:
    return next(c for c in filesystem_contracts() if c.canonical_id.endswith(suffix))


class FakeAction:
    name = "do_thing"
    description = "Does a thing."
    expected_result = "The thing is done."
    risk_tier = "reversible_write"
    permission_category = "filesystem"

    def required_parameters(self):
        return ["target"]


# =========================================================================
# A3 — extraction
# =========================================================================


def test_a_contract_is_derived_from_the_action_not_hand_written():
    contract = contract_from_action(FakeAction(), "Demo.DoThing", "demo")

    assert contract.canonical_id == "Demo.DoThing"
    assert contract.domain == "demo"
    assert contract.summary == "Does a thing."
    assert contract.metadata["source"] == SOURCE_ACTION
    assert contract.metadata["local_name"] == "do_thing"
    assert contract.metadata["expected_result"] == "The thing is done."


def test_extraction_publishes_the_required_argument_names():
    """The whole point. `CreateFolder` requires `name`; MB037's plan said
    `path` and nothing noticed until execution.

    UPDATED, deliberately: `CreateFolderAction` has since opted into
    publishing its optional arguments (`optional_parameters()`), which
    closes its schema. A wrong argument is therefore now caught as a
    wrong argument, not merely as a missing one -- which is a stronger
    form of exactly what this test was written to protect.
    """
    contract = contract_named("CreateFolder")

    assert contract.inputs.required_names == ("name",)
    errors = contract.accepts({"path": "demo"})
    assert "missing required argument: name" in errors
    assert any("path" in e for e in errors), "a closed schema must reject unknown args"
    assert contract.accepts({"name": "demo"}) == ()
    # The published optional argument is accepted, not treated as unknown.
    assert contract.accepts({"name": "demo", "location": "desktop"}) == ()


def test_an_extracted_schema_is_known_but_not_closed():
    """The required names are genuinely known; the optional ones are not
    published, so an unlisted argument is not an error.

    Re-pointed at `DeleteFolder`, which has not opted in.
    `CreateFolder` used to demonstrate this and no longer can -- it now
    publishes its optional arguments -- but the open-schema behaviour it
    was covering still exists for every action that has not opted in, so
    the coverage moves rather than disappears.
    """
    contract = contract_named("DeleteFolder")

    assert contract.inputs.known is True
    assert contract.inputs.closed is False


def test_an_action_that_opts_in_gets_a_closed_schema():
    """The other side of the same contract: opting in is what lets a
    caller trust the argument list is the whole story."""
    contract = contract_named("CreateFolder")

    assert contract.inputs.known is True
    assert contract.inputs.closed is True
    assert contract.accepts({"name": "demo", "location": "desktop"}) == ()


def test_extracted_arguments_carry_no_invented_type():
    """`required_parameters()` publishes names and nothing else.
    Defaulting to `string` would be right often enough to be trusted and
    wrong on every list argument."""
    contract = contract_named("CreateFolder")

    assert contract.inputs.field("name").type == UNKNOWN


def test_an_unknown_type_never_reports_a_type_mismatch():
    contract = contract_named("WorkspaceBootstrap")

    problems = contract.accepts({name: ["a list"] for name in contract.inputs.required_names})

    assert all("expected" not in problem for problem in problems)


def test_outputs_stay_unknown_because_expected_result_is_prose():
    contract = contract_named("CreateFolder")

    assert contract.outputs.known is False
    assert "expected_result" in contract.metadata


def test_permissions_are_mirrored_not_re_decided():
    assert contract_named("ReadFile").permissions.risk_tier == "read_only"
    assert contract_named("ReadFile").permissions.approval_required is False
    assert contract_named("DeleteFolder").permissions.approval_required is True


def test_side_effect_follows_the_declared_risk_tier():
    assert contract_named("ReadFile").side_effect == NO_EFFECT
    assert contract_named("CreateFolder").side_effect == REVERSIBLE
    assert contract_named("DeleteFolder").side_effect == IRREVERSIBLE


def test_latency_retryability_and_idempotency_are_never_derived():
    """Nothing in an Action declares them, so nothing may claim them."""
    contract = contract_named("CreateFolder")

    assert contract.latency_class == UNKNOWN
    assert contract.retryability == UNKNOWN
    assert contract.idempotency == UNKNOWN


def test_an_action_that_cannot_describe_itself_yields_an_unknown_schema():
    """Reflection is best-effort; one bad Action must not empty the
    registry."""

    class Broken(FakeAction):
        def required_parameters(self):
            raise RuntimeError("boom")

    contract = contract_from_action(Broken(), "Demo.Broken", "demo")

    assert contract.inputs.known is False


def test_every_filesystem_capability_produces_a_contract():
    contracts = filesystem_contracts()

    assert len(contracts) == len(filesystem_actions())
    assert all(c.canonical_id.startswith("Filesystem.") for c in contracts)


def test_extraction_uses_mission_controls_naming_rather_than_a_second_one():
    contract = contract_named("CreateFolder")

    assert contract.canonical_id == qualified_name("filesystem", "create_folder")


# =========================================================================
# A2 — the index
# =========================================================================


def test_an_index_entry_is_the_summary_a_prompt_needs():
    # DeleteFolder, not CreateFolder: CreateFolder now publishes its
    # optional arguments, so it is no longer an example of the
    # "arguments exist but were never published" shape this test covers.
    entry = entry_for(contract_named("DeleteFolder"))

    assert entry.canonical_id == "Filesystem.DeleteFolder"
    assert entry.required_args == ("path",)
    assert entry.args_complete is False
    assert entry.signature == "Filesystem.DeleteFolder(path, ...)"  # index form


def test_a_capability_with_no_published_arguments_says_so():
    entry = IndexEntry(canonical_id="X.Y", domain="x")

    assert entry.signature == "X.Y(...)"


def test_a_capability_that_genuinely_takes_nothing_is_distinguishable():
    entry = IndexEntry(canonical_id="X.Y", domain="x", args_complete=True)

    assert entry.signature == "X.Y()"


def test_the_index_is_sorted_so_the_prompt_is_deterministic():
    index = build_index(filesystem_contracts())

    assert list(index.names()) == sorted(index.names())
    assert build_index(filesystem_contracts()).as_dict() == index.as_dict()


def test_the_index_answers_the_cheap_questions_without_loading_anything():
    index = build_index(filesystem_contracts(), loader=lambda _id: None)

    assert len(index) == 14
    assert "Filesystem.CreateFolder" in index
    assert index.domains() == ("filesystem",)
    assert len(index.in_domain("filesystem")) == 14
    assert index.loaded == (), "the lazy tier was loaded to answer a summary question"


def test_search_matches_id_and_summary():
    index = build_index(filesystem_contracts())

    assert any(e.canonical_id == "Filesystem.CreateFolder" for e in index.search("createfolder"))
    assert index.search("") == ()
    assert index.search("nothing matches this") == ()


def test_a_full_contract_is_loaded_only_when_asked_and_then_remembered():
    calls: list[str] = []
    contracts = {c.canonical_id: c for c in filesystem_contracts()}

    def loader(canonical_id: str):
        calls.append(canonical_id)
        return contracts.get(canonical_id)

    index = build_index(contracts.values(), loader=loader)
    assert calls == []

    first = index.contract("Filesystem.CreateFolder")
    second = index.contract("Filesystem.CreateFolder")

    assert first is second
    assert calls == ["Filesystem.CreateFolder"], "the loader ran twice"
    assert index.loaded == ("Filesystem.CreateFolder",)


def test_a_capability_the_index_does_not_hold_loads_nothing():
    calls: list[str] = []
    index = build_index(filesystem_contracts(), loader=lambda i: calls.append(i))

    assert index.contract("Nope.Missing") is None
    assert calls == []


def test_a_loader_that_finds_nothing_is_not_asked_twice():
    calls: list[str] = []

    def loader(canonical_id: str):
        calls.append(canonical_id)

    index = build_index(filesystem_contracts(), loader=loader)
    index.contract("Filesystem.CreateFolder")
    index.contract("Filesystem.CreateFolder")

    assert calls == ["Filesystem.CreateFolder"]


def test_an_index_with_no_loader_reports_absence_rather_than_raising():
    index = build_index(filesystem_contracts())

    assert index.contract("Filesystem.CreateFolder") is None


def test_the_index_reports_which_capabilities_publish_nothing():
    index = build_index(
        (
            CapabilityContract(
                canonical_id="A.B", version=Version(1, 0, 0), domain="a", category="x"
            ),
        )
    )

    assert index.unspecified() == ("A.B",)


def test_an_unknown_input_schema_yields_no_required_args():
    contract = CapabilityContract(
        canonical_id="A.B",
        version=Version(1, 0, 0),
        domain="a",
        category="x",
        inputs=Schema.unknown(),
    )

    assert entry_for(contract).required_args == ()


def test_an_entry_is_reachable_by_id():
    index = build_index(filesystem_contracts())

    assert index.entry("Filesystem.CreateFolder").required_args == ("name",)
    assert index.entry("Nope.Missing") is None


def test_an_action_that_declares_nothing_reports_unknown_rather_than_empty():
    """A capability with no risk tier has not declared one; `""` would
    read as a declaration of nothing."""

    class Undeclared:
        name = "x"
        description = ""
        risk_tier = None
        permission_category = None

        def required_parameters(self):
            return []

    contract = contract_from_action(Undeclared(), "Demo.X", "demo")

    assert contract.permissions.risk_tier == UNKNOWN
    assert contract.side_effect == UNKNOWN
    assert contract.permissions.approval_required is False


def test_an_index_serialises_for_a_manifest():
    reported = build_index(filesystem_contracts()).as_dict()

    assert reported["count"] == 14
    assert reported["domains"] == ["filesystem"]
    assert reported["entries"][0]["required_args"]


# =========================================================================
# A4 — the Planner
# =========================================================================


def test_the_planner_catalogue_carries_argument_names_from_the_index():
    options = catalogue_from_index(build_index(filesystem_contracts()))

    create = next(o for o in options if o.name == "Filesystem.DeleteFolder")
    assert create.required_args == ("path",)
    assert create.args_complete is False


def test_the_capability_name_is_never_run_together_with_its_arguments():
    """A live run produced a plan whose capability was the literal string
    `Filesystem.WriteFile(path, ...)`. The name must stand alone."""
    options = catalogue_from_index(build_index(filesystem_contracts()))

    for line in render(options).splitlines():
        name = line.removeprefix("- ").split(" | ")[0]
        assert "(" not in name, line
        assert name in [o.name for o in options], line


def test_the_prompt_shows_the_signature_not_only_the_description():
    """The Planner must never have to read English to learn an argument's
    name."""
    options = catalogue_from_index(build_index(filesystem_contracts()))

    rendered = render(options)

    assert "Filesystem.DeleteFolder | args: path (others may exist)" in rendered
    assert "Filesystem.WriteFile | args: path (others may exist)" in rendered


def test_a_signature_distinguishes_undeclared_from_empty():
    from master_agent.planner.catalogue import CapabilityOption

    # The subject here is the ARGS distinction. Outputs are now stated on
    # every line for the same reason -- an absent field is not a fact --
    # so each expectation carries the outputs clause these options also
    # do not declare.
    outputs = " | outputs: none declared"
    assert signature(CapabilityOption("A.B")) == "args: none declared" + outputs
    assert (
        signature(CapabilityOption("A.B", args_complete=True))
        == "args: none" + outputs
    )
    assert (
        signature(CapabilityOption("A.B", required_args=("x",)))
        == "args: x (others may exist)" + outputs
    )
    assert (
        signature(CapabilityOption("A.B", required_args=("x",), args_complete=True))
        == "args: x" + outputs
    )


def test_the_mb037_plan_is_now_refused_before_it_is_submitted():
    """`{"path": "employee_api"}` against `Filesystem.CreateFolder`. This
    exact payload reached the Runtime in MB037 and failed there."""
    options = catalogue_from_index(build_index(filesystem_contracts()))

    plan, refusal = validate(
        document(step("s1", "Filesystem.CreateFolder", {"path": "employee_api"})),
        options,
    )

    assert plan is None
    assert refusal.code == BAD_PAYLOAD
    assert "`name`" in refusal.detail
    assert "It was given: path." in refusal.detail


def test_a_correct_payload_passes():
    options = catalogue_from_index(build_index(filesystem_contracts()))

    plan, refusal = validate(
        document(step("s1", "Filesystem.CreateFolder", {"name": "employee_api"})),
        options,
    )

    assert refusal is None
    assert plan.steps[0].payload == {"name": "employee_api"}


def test_optional_arguments_are_still_allowed_through():
    options = catalogue_from_index(build_index(filesystem_contracts()))

    _plan, refusal = validate(
        document(
            step(
                "s1",
                "Filesystem.CreateFolder",
                {"name": "demo", "location": "desktop"},
            )
        ),
        options,
    )

    assert refusal is None


def test_a_step_with_no_payload_at_all_is_refused_when_arguments_are_required():
    options = catalogue_from_index(build_index(filesystem_contracts()))

    plan, refusal = validate(
        document(
            {
                "id": "s1",
                "capability": "Filesystem.CreateFolder",
                "success": success(),
            }
        ),
        options,
    )

    assert plan is None
    assert refusal.code == BAD_PAYLOAD
    assert "It was given nothing." in refusal.detail


def test_a_capability_with_no_published_contract_constrains_nothing():
    """A stand-in rather than a raise: inventing requirements for an
    undescribed capability is the fabrication MB039 exists to remove."""
    from master_agent.planner.catalogue import CapabilityOption

    plan, refusal = validate(
        document(step("s1", "Legacy.Thing", {"anything": 1})),
        (CapabilityOption("Legacy.Thing"),),
    )

    assert refusal is None
    assert plan.steps[0].capability == "Legacy.Thing"


@pytest.mark.parametrize(
    ("capability", "wrong", "right"),
    [
        ("Filesystem.CreateFolder", "path", "name"),
        ("Filesystem.WriteFile", "file_path", "path"),
        ("Filesystem.ReadFile", "filename", "path"),
    ],
)
def test_the_argument_names_a_model_would_guess_are_caught(capability, wrong, right):
    """Every one of these is a name a language model plausibly invents,
    and two of them are names MB037's live plan actually produced."""
    options = catalogue_from_index(build_index(filesystem_contracts()))

    refusal = validate(
        document(step("s1", capability, {wrong: "x"})), options
    )[1]

    assert refusal.code == BAD_PAYLOAD
    assert f"`{right}`" in refusal.detail
