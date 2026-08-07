"""What a capability promises (Mission Brief 039).

MB036 and MB037 built a Planner that names the right capability and then
gets its arguments wrong, because the only thing published about a
capability is a sentence of prose. `Filesystem.CreateFolder` requires
`name`; the Planner wrote `path`. The plan read perfectly and could not
run.

A **contract** is the machine-readable answer to *"what does this
capability actually take, and what does calling it do to the world?"*

## Metadata only

Nothing in this package executes anything, imports an executor, or holds
a reference to a plugin instance. A contract describes; something else
performs. That separation is asserted by test, because a registry that
could invoke would become a second execution path and Constitution
Rule 4 gives Environment access exactly one door.

## Unknown stays UNKNOWN

Latency class, retryability and idempotency default to `UNKNOWN` and are
**never inferred from something else**. A capability that has not
declared its idempotency is not "probably idempotent"; it is unknown, and
a caller that needs to know must find out rather than be told a guess.

This is the same posture MB038 took toward provider throughput, and for
the same reason: a fabricated default is indistinguishable from a
measured one at the point of use, which is exactly when it does damage.

Side effects are the one exception, and a deliberate one -- see
`SIDE_EFFECT_BY_RISK`.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

#: The value every unmeasured, undeclared field carries. A string rather
#: than `None` so it survives serialisation intact and reads the same in
#: a JSON manifest as it does in Python.
UNKNOWN = "unknown"

# ---- side effects --------------------------------------------------------

NO_EFFECT = "none"
REVERSIBLE = "reversible"
IRREVERSIBLE = "irreversible"
SIDE_EFFECTS = (UNKNOWN, NO_EFFECT, REVERSIBLE, IRREVERSIBLE)

#: The one derivation this module permits, because it is a restatement
#: rather than a guess: `RiskTier` already *is* a statement about what
#: calling something does to the world, declared by the Action author and
#: gated by the Permission System. Reading it as a side effect adds no
#: information and invents none.
#:
#: Anything not in this map stays `UNKNOWN`.
SIDE_EFFECT_BY_RISK = {
    "read_only": NO_EFFECT,
    "reversible_write": REVERSIBLE,
    "irreversible": IRREVERSIBLE,
}

# ---- latency ------------------------------------------------------------
#
# Coarse buckets, not milliseconds. A capability's latency is a property
# of the machine it runs on, and MB038 already learned what happens when
# one laptop's numbers are treated as universal. These say what *kind* of
# wait a caller should expect; MB038's budgets say how long to allow.

INSTANT = "instant"
FAST = "fast"
SLOW = "slow"
VERY_SLOW = "very_slow"
LATENCY_CLASSES = (UNKNOWN, INSTANT, FAST, SLOW, VERY_SLOW)

# ---- retryability -------------------------------------------------------

RETRY_SAFE = "safe"
RETRY_UNSAFE = "unsafe"
RETRY_CONDITIONAL = "conditional"
RETRYABILITY = (UNKNOWN, RETRY_SAFE, RETRY_UNSAFE, RETRY_CONDITIONAL)

# ---- idempotency --------------------------------------------------------

IDEMPOTENT = "idempotent"
NOT_IDEMPOTENT = "not_idempotent"
IDEMPOTENCY = (UNKNOWN, IDEMPOTENT, NOT_IDEMPOTENT)

# ---- field types --------------------------------------------------------
#
# A closed, deliberately small set. This is a description of a payload a
# plugin already accepts, not a general-purpose type system: five types
# cover every Action in the codebase, and a bigger language is easy to
# grow into and hard to walk back (ENGINEERING_PRINCIPLES.md #10).

STRING = "string"
INTEGER = "integer"
NUMBER = "number"
BOOLEAN = "boolean"
OBJECT = "object"
ARRAY = "array"
#: The type nobody declared. `Action.required_parameters()` publishes
#: argument *names* and nothing else, so a contract extracted from one
#: knows what an argument is called and not what shape it takes.
#:
#: Defaulting those to `string` would be a fabrication that reads exactly
#: like a declaration -- and most Action arguments are strings, which is
#: what would make it dangerous: it would be right often enough to be
#: trusted and wrong on `folders`, `files` and every future list.
FIELD_TYPES = (UNKNOWN, STRING, INTEGER, NUMBER, BOOLEAN, OBJECT, ARRAY)

_VERSION = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


@dataclass(frozen=True, order=True)
class Version:
    """A semantic version for one capability's *contract*.

    Distinct from the plugin's version: a plugin can be rewritten without
    changing what it accepts, and a contract can change while the code
    around it does not. What a caller needs to know is whether the shape
    it was written against still holds.
    """

    major: int
    minor: int
    patch: int

    @classmethod
    def parse(cls, text: str) -> Version:
        match = _VERSION.match(text.strip())
        if match is None:
            raise ValueError(
                f"not a semantic version: {text!r} (expected MAJOR.MINOR.PATCH)"
            )
        return cls(*(int(part) for part in match.groups()))

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"

    def compatible_with(self, other: Version) -> bool:
        """Can a caller written against `other` still call this?

        Same major, and at least the minor it was written against. The
        ordinary semver reading, stated because the registry is the one
        place in Kalpavriksha where it will matter.
        """
        return self.major == other.major and self >= other


@dataclass(frozen=True)
class FieldSpec:
    """One argument a capability accepts.

    `description` is for a human and for a model; every other field is
    for a machine. The whole point of MB039 is that a caller no longer
    has to read the description to learn the argument's *name*.
    """

    name: str
    type: str = STRING
    required: bool = False
    description: str = ""
    #: A closed set of permitted values, when there is one. Empty means
    #: unconstrained -- **not** "any string is fine", which is a different
    #: claim nobody has made.
    choices: tuple[str, ...] = ()
    #: What the capability uses when the caller says nothing. `None` means
    #: there is no default and the field is simply absent.
    default: Any = None

    def __post_init__(self) -> None:
        if self.type not in FIELD_TYPES:
            raise ValueError(
                f"{self.name}: unknown field type {self.type!r}; "
                f"known: {', '.join(FIELD_TYPES)}"
            )

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "type": self.type,
            "required": self.required,
            "description": self.description,
            "choices": list(self.choices),
            "default": self.default,
        }


@dataclass(frozen=True)
class Schema:
    """The shape of a payload, in or out.

    `known` is False for a capability whose shape nobody has published.
    That is a **different fact** from a capability that takes no
    arguments, and conflating them is how a caller concludes an empty
    payload is correct when it is merely undescribed.
    """

    fields: tuple[FieldSpec, ...] = ()
    known: bool = True
    #: True when arguments beyond those listed are accepted. False means
    #: the list is exhaustive and an unexpected key is a caller error.
    closed: bool = True

    @staticmethod
    def unknown() -> Schema:
        """Nobody has published this shape. Says so, rather than
        pretending the capability takes nothing."""
        return Schema(fields=(), known=False, closed=False)

    @property
    def required_names(self) -> tuple[str, ...]:
        return tuple(spec.name for spec in self.fields if spec.required)

    @property
    def field_names(self) -> tuple[str, ...]:
        return tuple(spec.name for spec in self.fields)

    def field(self, name: str) -> FieldSpec | None:
        for spec in self.fields:
            if spec.name == name:
                return spec
        return None

    def problems(self, payload: dict[str, Any]) -> tuple[str, ...]:
        """Everything structurally wrong with this payload.

        **Structural only.** It checks names, presence and types; it never
        checks whether a path exists, a name is safe, or a folder is
        already there. Those are the Action's own `validate()`, which runs
        against the real world and remains the authority. This is the
        check that can happen *before* a plan is submitted, which is the
        whole point: MB037's plan named `path` where the Action wanted
        `name`, and nothing noticed until execution.

        An unknown schema produces no problems -- it cannot, having
        published nothing. Silence here is not approval.
        """
        if not self.known:
            return ()

        problems: list[str] = []
        for name in self.required_names:
            if name not in payload:
                problems.append(f"missing required argument: {name}")

        for key, value in payload.items():
            spec = self.field(key)
            if spec is None:
                if self.closed:
                    known = ", ".join(self.field_names) or "none"
                    problems.append(f"unexpected argument: {key} (accepts: {known})")
                continue
            if not _matches(value, spec.type):
                problems.append(
                    f"{key}: expected {spec.type}, got {type(value).__name__}"
                )
            elif spec.choices and value not in spec.choices:
                problems.append(
                    f"{key}: {value!r} is not one of {', '.join(spec.choices)}"
                )
        return tuple(problems)

    def as_dict(self) -> dict[str, Any]:
        return {
            "known": self.known,
            "closed": self.closed,
            "fields": [spec.as_dict() for spec in self.fields],
        }


def _matches(value: Any, expected: str) -> bool:
    """`bool` is checked before `int` deliberately: in Python `True` is an
    `int`, and a payload saying `True` where a count belongs is a mistake
    worth catching rather than silently reading as 1."""
    if expected == UNKNOWN:
        # Nobody declared a type, so nothing here can contradict one. The
        # *name* is still checked, which is the failure MB039 exists to
        # catch; a type check nobody published would be invented.
        return True
    if expected == BOOLEAN:
        return isinstance(value, bool)
    if expected == INTEGER:
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == NUMBER:
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == STRING:
        return isinstance(value, str)
    if expected == OBJECT:
        return isinstance(value, dict)
    if expected == ARRAY:
        return isinstance(value, (list, tuple))
    return False  # pragma: no cover - FieldSpec rejects unknown types


@dataclass(frozen=True)
class Permissions:
    """What calling this needs from the founder.

    Mirrored from the Action's own declaration rather than re-decided
    here. The Permission System remains the only thing that gates
    anything (MB028.0); this is the *description* of that gate, so a
    Planner can tell an irreversible step from a harmless one before
    proposing it.
    """

    risk_tier: str = UNKNOWN
    category: str = UNKNOWN
    #: True when a call will stop and wait for the founder. Derived from
    #: the risk tier by the same rule the Permission System applies, so
    #: the two cannot disagree.
    approval_required: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "risk_tier": self.risk_tier,
            "category": self.category,
            "approval_required": self.approval_required,
        }


@dataclass(frozen=True)
class CapabilityContract:
    """Everything published about one callable capability.

    Frozen, and every collection a tuple: a contract describes what a
    capability promised at the moment it was registered, and a consumer
    that could edit it would make "the registry is the source of truth"
    a convention rather than a property.
    """

    canonical_id: str
    version: Version
    domain: str
    category: str
    inputs: Schema = field(default_factory=Schema.unknown)
    outputs: Schema = field(default_factory=Schema.unknown)
    permissions: Permissions = field(default_factory=Permissions)
    side_effect: str = UNKNOWN
    latency_class: str = UNKNOWN
    retryability: str = UNKNOWN
    idempotency: str = UNKNOWN
    summary: str = ""
    #: Free-form, for whatever a source knows and this shape does not
    #: model. Never read to make a decision -- a field nobody validates
    #: must not become load-bearing.
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for value, allowed, label in (
            (self.side_effect, SIDE_EFFECTS, "side_effect"),
            (self.latency_class, LATENCY_CLASSES, "latency_class"),
            (self.retryability, RETRYABILITY, "retryability"),
            (self.idempotency, IDEMPOTENCY, "idempotency"),
        ):
            if value not in allowed:
                raise ValueError(
                    f"{self.canonical_id}: {label}={value!r} is not one of "
                    f"{', '.join(allowed)}"
                )
        if not self.canonical_id.strip():
            raise ValueError("a contract needs a canonical id")

    # ---- reading ---------------------------------------------------------

    @property
    def fully_specified(self) -> bool:
        """Is every field of this contract actually known?

        Most are not, today, and that is the honest starting point. A
        registry that reported everything as specified would be describing
        a codebase that does not exist yet.
        """
        return (
            self.inputs.known
            and self.outputs.known
            and UNKNOWN
            not in (
                self.side_effect,
                self.latency_class,
                self.retryability,
                self.idempotency,
            )
        )

    @property
    def unknowns(self) -> tuple[str, ...]:
        """Which fields nobody has declared. The work list for making a
        capability fully contracted, and the honest answer to "how much of
        this registry is real?"."""
        missing = []
        if not self.inputs.known:
            missing.append("inputs")
        if not self.outputs.known:
            missing.append("outputs")
        for value, label in (
            (self.side_effect, "side_effect"),
            (self.latency_class, "latency_class"),
            (self.retryability, "retryability"),
            (self.idempotency, "idempotency"),
        ):
            if value == UNKNOWN:
                missing.append(label)
        return tuple(missing)

    def accepts(self, payload: dict[str, Any]) -> tuple[str, ...]:
        """Structural problems with this payload, or nothing. See
        `Schema.problems` for what this does and does not check."""
        return self.inputs.problems(payload)

    def as_dict(self) -> dict[str, Any]:
        return {
            "canonical_id": self.canonical_id,
            "version": str(self.version),
            "domain": self.domain,
            "category": self.category,
            "inputs": self.inputs.as_dict(),
            "outputs": self.outputs.as_dict(),
            "permissions": self.permissions.as_dict(),
            "side_effect": self.side_effect,
            "latency_class": self.latency_class,
            "retryability": self.retryability,
            "idempotency": self.idempotency,
            "summary": self.summary,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, document: dict[str, Any]) -> CapabilityContract:
        return cls(
            canonical_id=document["canonical_id"],
            version=Version.parse(document.get("version", "0.0.0")),
            domain=document.get("domain", ""),
            category=document.get("category", UNKNOWN),
            inputs=_schema_from(document.get("inputs")),
            outputs=_schema_from(document.get("outputs")),
            permissions=Permissions(
                risk_tier=(document.get("permissions") or {}).get("risk_tier", UNKNOWN),
                category=(document.get("permissions") or {}).get("category", UNKNOWN),
                approval_required=(document.get("permissions") or {}).get(
                    "approval_required", False
                ),
            ),
            side_effect=document.get("side_effect", UNKNOWN),
            latency_class=document.get("latency_class", UNKNOWN),
            retryability=document.get("retryability", UNKNOWN),
            idempotency=document.get("idempotency", UNKNOWN),
            summary=document.get("summary", ""),
            metadata=dict(document.get("metadata") or {}),
        )


def _schema_from(document: Any) -> Schema:
    """A missing schema is an **unknown** schema, never an empty one.

    The distinction is the whole reason `Schema.known` exists: a manifest
    that omits `inputs` is silent about them, and reading that silence as
    "takes no arguments" is how a caller decides `{}` is correct.
    """
    if not document:
        return Schema.unknown()
    return Schema(
        fields=tuple(
            FieldSpec(
                name=row["name"],
                type=row.get("type", STRING),
                required=row.get("required", False),
                description=row.get("description", ""),
                choices=tuple(row.get("choices") or ()),
                default=row.get("default"),
            )
            for row in document.get("fields") or ()
        ),
        known=document.get("known", True),
        closed=document.get("closed", True),
    )
