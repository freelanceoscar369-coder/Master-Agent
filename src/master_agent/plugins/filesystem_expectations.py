"""What a filesystem Step's claim looks like when checked against a disk.

## Why this exists

The Planner states *what a Step is meant to accomplish*; it does not know
what a filesystem observation looks like, and it must not learn. So every
Step arrives carrying `SuccessSpec(...).to_expected_outcome()`, built by
MB035's text builder, which always emits `field="empty"` -- correct for
`TextVerifier`, whose observation has an `empty` field, and meaningless
against a `FilesystemObservation`, whose fields are `target_exists`,
`target_is_dir`, `target_path` and friends.

Measured, before this module existed:

    ExpectedOutcome the Planner attaches -> field='empty' equals False
    filesystem observation               -> has no 'empty' field
    verdict for a folder that DID exist  -> not_matched
                                            "field 'empty' not present"

So Verification could not simply be switched on: it would have called a
correct folder wrong.

## The division of labour

The Planner owns **what this Step is for** -- carried through unchanged as
the description. This module owns **how that claim is checked against a
real disk**, because the filesystem package is what knows the shape of a
filesystem observation. The Runtime owns neither and constructs no checks.

The `MissionPlan` is never rewritten. This produces an *effective*
expectation used for one verification, and the `Evidence` records the
checks that were actually evaluated.

## What this deliberately does NOT do

It compares **the Step's own payload** against the world. It does not
reinterpret what Onkar meant. A Step whose payload says

    location = "Desktop", path = "Desktop/Test/file.txt"

is verified against exactly that target, and if the file is there the
verdict is MATCHED -- even though a founder who said "put it on the
Desktop" probably did not mean a `Desktop` folder inside the Desktop.
Whether that was the right Step is a question about Intent, answered by
the capability contract the Planner reads and later by outcome
conformance. Verification that quietly judged founder meaning would
become a second, unaccountable Planner.
"""
from __future__ import annotations

from typing import Any

from master_agent.verification.evidence import ExpectedOutcome, ObservationCheck

#: Capabilities whose whole point is that the target stops existing.
_ABSENCE: frozenset[str] = frozenset({"delete_file", "delete_folder"})

#: Capabilities that must leave a directory behind.
_DIRECTORY: frozenset[str] = frozenset({"create_folder", "workspace_bootstrap"})

#: Capabilities that must leave a file behind.
_FILE: frozenset[str] = frozenset(
    {"write_file", "append_file", "copy_file", "move_file", "rename_file"}
)

#: Capabilities whose exact resulting content is knowable from the payload
#: alone. `append_file` is deliberately absent: the finished file is prior
#: content plus this step's, and this layer never saw the prior content,
#: so a digest built from the payload would fail a correct append.
_EXACT_CONTENT: frozenset[str] = frozenset({"write_file"})

#: Capabilities that answer a question instead of changing the world.
#:
#: These have NO domain verification, on purpose. A target-exists check
#: would be actively wrong here: `file_exists` reporting `False` about a
#: file that is genuinely absent is a *correct* execution, and an
#: existence check would mark it failed. Verifying a query means checking
#: that its answer matches reality, which is a different observation from
#: "what is at this path", and it is not built yet.
_QUERY: frozenset[str] = frozenset(
    {"read_file", "list_directory", "search_files", "file_exists", "directory_exists"}
)


def _local(capability: str) -> str:
    """`Filesystem.CreateFolder`, `CreateFolder` and `create_folder` name
    the same capability three ways -- the qualified catalogue name, the
    contract class, and the action constant."""
    return capability.rsplit(".", 1)[-1].replace("_", "").replace("-", "").lower()


def _in(capability: str, names: frozenset[str]) -> bool:
    wanted = _local(capability)
    return any(_local(name) == wanted for name in names)


def supports(capability: str) -> bool:
    """Can this module state a disk-checkable expectation for `capability`?

    `False` is not a failure and not a pass: under the fail-closed runtime
    it means the Step cannot claim completion, which is the truthful
    answer while a capability has no domain verification yet.
    """
    return _in(capability, _ABSENCE) or _in(capability, _DIRECTORY) or _in(capability, _FILE)


def relative_target(payload: dict[str, Any]) -> str:
    """The path this Step is about, relative to its named `location`.

    Reads the SAME keys the actions read, in the same order, so
    verification cannot end up checking a different file from the one
    execution touched. `destination` precedes `source` because for a copy
    or a move the new file is the effect being claimed.
    """
    for key in ("path", "name", "destination", "source"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip().replace("\\", "/")
    return "."


def expected_content(payload: dict[str, Any]) -> str | None:
    """The exact text this Step said it would write, or `None`."""
    content = payload.get("content")
    return content if isinstance(content, str) else None


def wants_content_digest(capability: str, payload: dict[str, Any]) -> bool:
    """Should the observation pay for a content digest?

    Only where the finished content is knowable from the payload and there
    is something to compare against. A digest is cheap but not free, and
    Verification re-observes on every verified step.
    """
    return _in(capability, _EXACT_CONTENT) and expected_content(payload) is not None


def bind_for_environment(
    capability: str,
    payload: dict[str, Any],
    description: str,
) -> ExpectedOutcome | None:
    """The Planner's claim, expressed as checks a disk can answer.

    `description` travels through untouched: it is the Planner's sentence
    about what the Step is for, and nothing here reinterprets it. Only the
    checks are ours, derived mechanically from the capability and its
    payload -- never by reading the description as prose.

    Returns `None` when this capability has no disk-checkable effect, so
    the caller produces no Evidence rather than a fabricated verdict.
    """
    if not supports(capability):
        return None

    checks: list[ObservationCheck] = []
    target = relative_target(payload)

    if _in(capability, _ABSENCE):
        # Absence IS the expected environmental fact. Checking
        # `target_exists == False` is the whole verification; asking for a
        # path or a type as well would fail on a target correctly gone.
        return ExpectedOutcome(
            description=description,
            checks=[ObservationCheck(
                field="target_exists", operator="equals", value=False,
                description=f"'{target}' no longer exists",
            )],
        )

    checks.append(ObservationCheck(
        field="target_exists", operator="equals", value=True,
        description=f"'{target}' exists on disk",
    ))
    # Compares against the path the STEP asked for, not against anything
    # this layer imagines the founder meant. See the module docstring.
    checks.append(ObservationCheck(
        field="target_path", operator="equals", value=target,
        description=f"the target sits at '{target}' relative to its location",
    ))

    if _in(capability, _DIRECTORY):
        checks.append(ObservationCheck(
            field="target_is_dir", operator="equals", value=True,
            description=f"'{target}' is a directory",
        ))
        return ExpectedOutcome(description=description, checks=checks)

    checks.append(ObservationCheck(
        field="target_is_dir", operator="equals", value=False,
        description=f"'{target}' is a file",
    ))

    content = expected_content(payload)
    if _in(capability, _EXACT_CONTENT) and content is not None:
        import hashlib

        from master_agent.plugins.filesystem_observation import normalise_text

        checks.append(ObservationCheck(
            field="content_text_sha256",
            operator="equals",
            value=hashlib.sha256(normalise_text(content).encode("utf-8")).hexdigest(),
            # A digest, not a preview. `content_preview` is capped, so it
            # can show that a file STARTS a certain way and never that it
            # IS a certain thing -- and claiming exact-content verification
            # from a truncated prefix would be the same class of lie this
            # repair exists to stop. An unreadable file yields no digest,
            # the check cannot find its field, and the verdict is honestly
            # not a pass.
            description="the file holds exactly the text the step said it would write",
        ))

    return ExpectedOutcome(description=description, checks=checks)
