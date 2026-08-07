"""MB039 Stage A1 — the capability contract model.

The property under test throughout: **a contract says what is known and
says `unknown` for the rest.** MB036 and MB037 both failed because
silence about an argument was read as agreement about it.
"""
from __future__ import annotations

import ast
import json
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from master_agent.capabilities.contract import (
    ARRAY,
    BOOLEAN,
    IDEMPOTENT,
    INSTANT,
    INTEGER,
    IRREVERSIBLE,
    NO_EFFECT,
    NUMBER,
    OBJECT,
    RETRY_SAFE,
    RETRY_UNSAFE,
    REVERSIBLE,
    SIDE_EFFECT_BY_RISK,
    STRING,
    UNKNOWN,
    CapabilityContract,
    FieldSpec,
    Permissions,
    Schema,
    Version,
)

PACKAGE = Path(__file__).resolve().parents[1] / "src" / "master_agent" / "capabilities"


def contract(**overrides) -> CapabilityContract:
    fields = {
        "canonical_id": "Filesystem.CreateFolder",
        "version": Version(1, 0, 0),
        "domain": "filesystem",
        "category": "filesystem",
    }
    fields.update(overrides)
    return CapabilityContract(**fields)


# ---- versions ------------------------------------------------------------


def test_a_version_parses_and_renders_round_trip():
    assert str(Version.parse("2.11.3")) == "2.11.3"
    assert Version.parse(" 1.0.0 ") == Version(1, 0, 0)


@pytest.mark.parametrize("text", ["1.0", "v1.0.0", "1.0.0-beta", "", "abc"])
def test_a_malformed_version_is_refused_rather_than_coerced(text):
    with pytest.raises(ValueError) as caught:
        Version.parse(text)

    assert "semantic version" in str(caught.value)


def test_versions_order_by_significance():
    assert Version(1, 2, 0) > Version(1, 1, 9)
    assert Version(2, 0, 0) > Version(1, 99, 99)


def test_compatibility_needs_the_same_major_and_at_least_the_minor():
    written_against = Version(1, 2, 0)

    assert Version(1, 2, 0).compatible_with(written_against) is True
    assert Version(1, 3, 0).compatible_with(written_against) is True
    assert Version(1, 1, 0).compatible_with(written_against) is False
    assert Version(2, 0, 0).compatible_with(written_against) is False


# ---- field specs ---------------------------------------------------------


def test_an_unknown_field_type_is_refused_at_construction():
    with pytest.raises(ValueError) as caught:
        FieldSpec(name="path", type="pathlike")

    assert "unknown field type" in str(caught.value)
    assert "string" in str(caught.value), "the error does not list what is known"


def test_a_field_spec_is_frozen():
    with pytest.raises(FrozenInstanceError):
        FieldSpec(name="path").required = True  # type: ignore[misc]


# ---- schemas: known, unknown, and the difference -------------------------


def test_an_unknown_schema_is_not_an_empty_one():
    """The distinction MB036 Finding 4 turns on: silence about arguments
    is not a statement that there are none."""
    unknown = Schema.unknown()
    empty = Schema(fields=())

    assert unknown.known is False
    assert empty.known is True
    assert unknown != empty


def test_an_unknown_schema_reports_no_problems_because_it_knows_nothing():
    """Silence here is not approval -- it is the absence of an opinion."""
    assert Schema.unknown().problems({"anything": 1}) == ()


def test_a_missing_required_argument_is_the_mb037_failure():
    """`Filesystem.CreateFolder` wants `name`; the plan said `path`."""
    schema = Schema(fields=(FieldSpec("name", STRING, required=True),))

    problems = schema.problems({"path": "employee_api"})

    assert any("missing required argument: name" in p for p in problems)
    assert any("unexpected argument: path" in p for p in problems)


def test_an_unexpected_argument_names_what_is_accepted():
    """A founder should not have to go and look."""
    schema = Schema(fields=(FieldSpec("name"), FieldSpec("location")))

    problems = schema.problems({"path": "x"})

    assert "accepts: name, location" in problems[0]


def test_an_open_schema_tolerates_extra_arguments():
    schema = Schema(fields=(FieldSpec("name"),), closed=False)

    assert schema.problems({"name": "x", "extra": 1}) == ()


def test_a_satisfied_schema_reports_nothing():
    schema = Schema(
        fields=(FieldSpec("name", STRING, required=True), FieldSpec("location"))
    )

    assert schema.problems({"name": "demo", "location": "desktop"}) == ()


@pytest.mark.parametrize(
    ("declared", "value", "ok"),
    [
        (STRING, "x", True), (STRING, 1, False),
        (INTEGER, 3, True), (INTEGER, 3.5, False),
        (NUMBER, 3, True), (NUMBER, 3.5, True), (NUMBER, "3", False),
        (BOOLEAN, True, True), (BOOLEAN, 1, False),
        (OBJECT, {}, True), (OBJECT, [], False),
        (ARRAY, [], True), (ARRAY, (), True), (ARRAY, {}, False),
    ],
)
def test_types_are_checked_structurally(declared, value, ok):
    schema = Schema(fields=(FieldSpec("v", declared),))

    assert (schema.problems({"v": value}) == ()) is ok


def test_a_boolean_is_never_accepted_as_an_integer():
    """`True` is an `int` in Python. A payload saying `True` where a count
    belongs is a mistake worth catching, not silently reading as 1."""
    schema = Schema(fields=(FieldSpec("count", INTEGER),))

    assert schema.problems({"count": True}) != ()


def test_a_value_outside_a_closed_set_is_refused():
    schema = Schema(
        fields=(FieldSpec("location", STRING, choices=("desktop", "documents")),)
    )

    assert schema.problems({"location": "desktop"}) == ()
    assert "is not one of desktop, documents" in schema.problems({"location": "c:/"})[0]


def test_empty_choices_constrain_nothing():
    schema = Schema(fields=(FieldSpec("free", STRING),))

    assert schema.problems({"free": "anything at all"}) == ()


def test_a_schema_reports_its_own_shape():
    schema = Schema(
        fields=(FieldSpec("name", required=True), FieldSpec("location"))
    )

    assert schema.required_names == ("name",)
    assert schema.field_names == ("name", "location")
    assert schema.field("location").name == "location"
    assert schema.field("absent") is None


# ---- the contract --------------------------------------------------------


def test_a_contract_defaults_every_undeclared_field_to_unknown():
    """Nothing is inferred. A capability that has not declared its
    idempotency is not 'probably idempotent'."""
    subject = contract()

    assert subject.side_effect == UNKNOWN
    assert subject.latency_class == UNKNOWN
    assert subject.retryability == UNKNOWN
    assert subject.idempotency == UNKNOWN
    assert subject.inputs.known is False
    assert subject.outputs.known is False


def test_a_contract_lists_what_nobody_has_declared():
    """The work list for making a capability fully contracted, and the
    honest answer to 'how much of this registry is real?'."""
    assert contract().unknowns == (
        "inputs",
        "outputs",
        "side_effect",
        "latency_class",
        "retryability",
        "idempotency",
    )


def test_a_fully_declared_contract_says_so():
    subject = contract(
        inputs=Schema(fields=(FieldSpec("name", required=True),)),
        outputs=Schema(fields=(FieldSpec("created", BOOLEAN),)),
        side_effect=REVERSIBLE,
        latency_class=INSTANT,
        retryability=RETRY_SAFE,
        idempotency=IDEMPOTENT,
    )

    assert subject.fully_specified is True
    assert subject.unknowns == ()


def test_a_contract_with_one_gap_is_not_fully_specified():
    subject = contract(
        inputs=Schema(fields=()),
        outputs=Schema(fields=()),
        side_effect=REVERSIBLE,
        latency_class=INSTANT,
        retryability=RETRY_SAFE,
    )

    assert subject.fully_specified is False
    assert subject.unknowns == ("idempotency",)


@pytest.mark.parametrize(
    ("field_name", "bad"),
    [
        ("side_effect", "maybe"),
        ("latency_class", "quick"),
        ("retryability", "sometimes"),
        ("idempotency", "mostly"),
    ],
)
def test_a_value_outside_a_closed_vocabulary_is_refused(field_name, bad):
    with pytest.raises(ValueError) as caught:
        contract(**{field_name: bad})

    assert field_name in str(caught.value)


def test_a_contract_needs_an_identity():
    with pytest.raises(ValueError):
        contract(canonical_id="   ")


def test_a_contract_is_frozen():
    with pytest.raises(FrozenInstanceError):
        contract().latency_class = INSTANT  # type: ignore[misc]


def test_a_contract_checks_a_payload_without_running_anything():
    subject = contract(inputs=Schema(fields=(FieldSpec("name", required=True),)))

    assert subject.accepts({"name": "demo"}) == ()
    assert subject.accepts({"path": "demo"}) != ()


# ---- the one permitted derivation ---------------------------------------


def test_side_effect_is_read_from_the_risk_tier_and_nothing_else():
    """`RiskTier` already *is* a statement about what calling something
    does to the world. Reading it adds no information and invents none."""
    assert SIDE_EFFECT_BY_RISK["read_only"] == NO_EFFECT
    assert SIDE_EFFECT_BY_RISK["reversible_write"] == REVERSIBLE
    assert SIDE_EFFECT_BY_RISK["irreversible"] == IRREVERSIBLE


def test_an_unrecognised_risk_tier_maps_to_nothing():
    assert "something_new" not in SIDE_EFFECT_BY_RISK


# ---- serialisation -------------------------------------------------------


def test_a_contract_round_trips_through_plain_json():
    original = contract(
        inputs=Schema(
            fields=(
                FieldSpec("name", STRING, required=True, description="folder name"),
                FieldSpec("location", STRING, choices=("desktop",), default="desktop"),
            )
        ),
        outputs=Schema(fields=(FieldSpec("path", STRING),)),
        permissions=Permissions("reversible_write", "filesystem", True),
        side_effect=REVERSIBLE,
        latency_class=INSTANT,
        retryability=RETRY_UNSAFE,
        idempotency=IDEMPOTENT,
        summary="Create a folder.",
        metadata={"source": "action"},
    )

    document = json.loads(json.dumps(original.as_dict()))
    restored = CapabilityContract.from_dict(document)

    assert restored == original


def test_a_manifest_that_omits_a_schema_reads_as_unknown_not_empty():
    """A manifest silent about inputs is silent, not a claim that the
    capability takes none. This is the bug MB039 exists to prevent."""
    restored = CapabilityContract.from_dict(
        {"canonical_id": "X.Y", "version": "1.0.0"}
    )

    assert restored.inputs.known is False
    assert restored.outputs.known is False
    assert restored.side_effect == UNKNOWN


def test_an_explicitly_empty_schema_survives_as_empty():
    """A capability that genuinely takes no arguments must be able to say
    so, distinguishably."""
    restored = CapabilityContract.from_dict(
        {
            "canonical_id": "Desktop.ScanMachine",
            "version": "1.0.0",
            "inputs": {"known": True, "closed": True, "fields": []},
        }
    )

    assert restored.inputs.known is True
    assert restored.inputs.field_names == ()


# ---- metadata only -------------------------------------------------------


def test_the_package_cannot_execute_anything():
    """A registry that could invoke would be a second execution path, and
    Constitution Rule 4 gives Environment access exactly one door."""
    forbidden = {"subprocess", "os", "socket", "urllib", "httpx", "requests", "pathlib"}
    for path in sorted(PACKAGE.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name.split(".")[0] not in forbidden, path.name
            elif isinstance(node, ast.ImportFrom) and node.module:
                assert node.module.split(".")[0] not in forbidden, path.name
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id not in {"open", "exec", "eval"}, path.name


def _code_only(path: Path) -> str:
    """Source with docstrings stripped.

    The word `executor` in a docstring saying "this package holds no
    executor" is documentation; the same word in a call is a defect. A
    grep over raw source cannot tell them apart -- MB033 found a test that
    passed on a substring for want of this, and the first version of
    *this* test failed on its own docstring.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef):
            body = node.body
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                node.body = body[1:] or [ast.Pass()]
    return ast.unparse(tree).lower()


def test_the_package_holds_no_reference_to_an_executor_or_plugin():
    for path in sorted(PACKAGE.glob("*.py")):
        source = _code_only(path)
        for word in ("executor", "invoke(", "def run(", ".complete("):
            assert word not in source, f"{path.name} contains {word!r}"
