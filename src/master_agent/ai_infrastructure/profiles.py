"""Supplying the Broker with provider profiles (Mission Brief 032
Deliverable 3).

> The Broker consumes an inventory; it never produces one. — ADR-0017

This module is the consuming half. It reads the **Desktop Executive's last
machine scan** — the one the Dashboard already reads (MB030, ADR-0016
Decision 5) — and turns it into `ProviderProfile`s the Broker can decide
over. It scans nothing itself: no `subprocess`, no filesystem, no probing.
Environment access has exactly one door and this is not it (Constitution
Rule 4).

Three availability rules, and each one reports a *fact*:

| Spec | Available when |
|---|---|
| inventory-backed, scan present | the machine scan says it is installed and healthy |
| inventory-backed, no scan yet | **no** — "not scanned" is not "installed" (ADR-0016) |
| credentialled service | the founder enabled it in configuration |

The middle row matters. A launcher that assumed local providers were
present until proven otherwise would select one and fail at call time,
which is precisely the "fail later" MB032 Deliverable 4 exists to stop.
The launcher submits a machine scan at startup and profiles are rebuilt on
every request, so the estate fills in as soon as the Runtime has run it.

**Nothing here ranks.** No sorting by quality, no preference, no "best".
ADR-0018's Consequences name a ranking function growing outside the Broker
as *the* single failure mode that would invalidate the design;
`tests/test_broker_integration.py` asserts this package holds none.
"""
from __future__ import annotations

from typing import Any

from master_agent.broker.registry import (
    EconomicClass,
    ProviderDescriptor,
    RegistrationProvenance,
)
from master_agent.ai_infrastructure.catalog import PROVIDER_CATALOG, ProviderSpec, is_coding_agent
from master_agent.broker.profiles import ProviderProfile

#: Why a provider is not available, in a sentence a founder can act on —
#: the same discipline the Broker applies to its rejection reasons.
NOT_SCANNED = "no machine scan has run yet"
NOT_INSTALLED = "not installed on this machine"
NOT_HEALTHY = "installed but not answering"
NO_CREDENTIALS = "no credentials configured; enable it to make it selectable"
INSTALLED = "installed"
AUTONOMOUS_REASONING_UNSAFE = "AUTONOMOUS_REASONING_UNSAFE"
CODING_AGENT_NOT_A_REASONING_PROVIDER = (
    "CODING_AGENT_NOT_A_REASONING_PROVIDER: this identity is a coding tool, "
    "never a reasoning provider, regardless of installation state"
)


class ProviderSource:
    """Builds the estate the Broker chooses from, fresh on every request.

    `inventory_provider` is the same zero-argument callable the Dashboard
    is given (`lambda: desktop.cached_inventory`) — a *read* of what was
    last observed, never a scan. It may return None, and returning None is
    a normal state on a system that has just started.

    Rebuilt per call rather than cached because availability is exactly the
    thing that changes underneath you: a provider that was down at boot and
    is up now should be selectable now, and a cached estate is how a system
    ends up confidently refusing work it could do.
    """

    def __init__(
        self,
        inventory_provider: Any = None,
        registry: Any = None,
        enabled_cloud_providers: tuple[str, ...] | frozenset[str] = (),
        executable_provider_ids: Any = None,
        specs: tuple[ProviderSpec, ...] | None = None,
    ) -> None:
        """`registry` is the canonical `ProviderRegistry` and is the only
        source of administrative provider facts.

        It used to take `specs` and project straight from
        `PROVIDER_CATALOG`, which meant the catalogue remained a
        production authority for the life of the process: a descriptor
        registered administratively was invisible to selection, and
        editing a spec silently changed what the Broker saw. The
        catalogue is now a bootstrap import and nothing else.

        `executable_provider_ids` is a callable returning the ids that
        currently have a registered executable implementation. Optional,
        and when absent this projection makes no claim about
        executability -- exactly as before. When supplied, a descriptor
        with no live implementation is reported unavailable, because
        KNOWN is not EXECUTABLE and a restored binding is not evidence
        that anything is callable now.
        """
        self._inventory_provider = inventory_provider
        self._enabled = frozenset(enabled_cloud_providers)
        self._executable_provider_ids = executable_provider_ids

        # `specs` is BOOTSTRAP, not an authority. Given some, they are
        # imported into a registry once, here, and never read again -- so
        # `profiles()` always projects from canonical descriptors whichever
        # way this was constructed, and editing a `ProviderSpec` after
        # construction cannot silently change a `ProviderProfile`. That
        # last property is what "canonical" has to mean; a source that
        # re-read the catalogue on every call did not have it.
        if registry is None:
            from master_agent.broker.registry import ProviderRegistry

            registry = ProviderRegistry()
            for spec in (PROVIDER_CATALOG if specs is None else specs):
                registry.register(descriptor_for(spec))
        self._registry = registry

    @property
    def registry(self) -> Any:
        return self._registry

    @property
    def enabled_cloud_providers(self) -> frozenset[str]:
        return self._enabled

    # ---- the estate ----------------------------------------------------

    def profiles(self) -> tuple[ProviderProfile, ...]:
        inventory = self._inventory()
        executable = self._executable()
        return tuple(
            profile_from_descriptor(descriptor, inventory, self._enabled, executable)
            for descriptor in self._descriptors()
        )

    def _descriptors(self) -> tuple[Any, ...]:
        if self._registry is None:
            return ()
        try:
            return tuple(self._registry.all())
        except Exception:  # noqa: BLE001 - an unreadable registry is an empty estate
            return ()

    def _executable(self) -> frozenset[str] | None:
        """Which providers currently have a live implementation, or None
        when nobody said. None means "no claim", not "none of them"."""
        if self._executable_provider_ids is None:
            return None
        try:
            return frozenset(self._executable_provider_ids())
        except Exception:  # noqa: BLE001
            return None

    def available(self) -> tuple[ProviderProfile, ...]:
        return tuple(profile for profile in self.profiles() if profile.available)

    def counts(self) -> tuple[int, int]:
        """(available, total). Two numbers a boot report can state without
        anyone having to interpret a list."""
        profiles = self.profiles()
        return sum(1 for profile in profiles if profile.available), len(profiles)

    def has_scan(self) -> bool:
        return self._inventory() is not None

    def _inventory(self) -> Any:
        """A read that fails is absent data, never an exception thrown at
        whoever asked for a provider — the same tolerance
        `DashboardSources` applies to every read it makes."""
        if self._inventory_provider is None:
            return None
        try:
            return self._inventory_provider()
        except Exception:  # noqa: BLE001 - an unreadable scan is simply no scan
            return None


def profile_for(
    spec: ProviderSpec,
    inventory: Any = None,
    enabled: frozenset[str] | tuple[str, ...] = (),
) -> ProviderProfile:
    """One spec plus what the machine says about it, as a Broker profile.

    `benchmark` is always None: nothing in this build measures a provider,
    so `quality` is the declared number and the profile says so rather than
    presenting a claim as evidence (ADR-0017 Decision 5).
    """
    available, detail = availability(spec, inventory, frozenset(enabled))
    return ProviderProfile(
        provider_id=spec.provider_id,
        capabilities=frozenset(spec.capabilities),
        locality=spec.locality,
        privacy=spec.privacy,
        quality=spec.declared_quality,
        benchmark=None,
        benchmark_confidence=0.0,
        cost=spec.cost_per_call,
        latency_ms=spec.latency_ms,
        available=available,
        requires_network=spec.requires_network,
        requires_approval=spec.requires_approval,
        max_context_tokens=spec.max_context_tokens,
        notes=detail,
        prefill_tokens_per_second=spec.prefill_tokens_per_second,
        decode_tokens_per_second=spec.decode_tokens_per_second,
        expected_itl_ms=spec.expected_itl_ms,
        supports_streaming=spec.supports_streaming,
        chars_per_token=spec.chars_per_token,
        serialises=spec.serialises,
        model_load_ms=spec.model_load_ms,
    )


def availability(
    spec: ProviderSpec,
    inventory: Any = None,
    enabled: frozenset[str] = frozenset(),
) -> tuple[bool, str]:
    """Is this provider usable right now, and how do we know?

    Returns `(available, detail)` — never a bare boolean, because "not
    available" and "not available *because nothing has looked*" are
    different facts and a founder deciding whether to install something
    needs the second one.
    """
    if is_coding_agent(spec):
        return False, CODING_AGENT_NOT_A_REASONING_PROVIDER

    if spec.autonomous_reasoning_unsafe_reason is not None:
        return False, f"{AUTONOMOUS_REASONING_UNSAFE}: {spec.autonomous_reasoning_unsafe_reason}"

    if spec.needs_credentials and spec.provider_id not in enabled:
        return False, NO_CREDENTIALS

    if spec.inventory_key is None:
        return True, spec.notes or "configured"

    if inventory is None:
        return False, NOT_SCANNED

    application = inventory.get(spec.inventory_key)
    if application is None or not getattr(application, "installed", False):
        return False, NOT_INSTALLED
    if not getattr(application, "healthy", True):
        return False, NOT_HEALTHY

    version = getattr(application, "version", None)
    return True, f"{INSTALLED}{f' {version}' if version else ''}"


# ---- bootstrap: the catalogue becomes registry descriptors --------------
#
# `ProviderRegistry` is the canonical administrative record and
# `PROVIDER_CATALOG` is a declared bootstrap source. Until now production
# never joined them: `ProviderSource` authored profiles straight from
# specs, so the catalogue stayed a second independent authority for the
# life of the process and anything registered administratively was
# invisible to selection.
#
# This is the join, and it is deliberately a one-way import. After
# bootstrap the registry is the authority; the catalogue is where the
# founder's declared estate came FROM, not a parallel truth.


def descriptor_for(spec: ProviderSpec) -> ProviderDescriptor:
    """One catalogue spec as the canonical descriptor of the same
    provider.

    Every field carried across is one `ProviderSpec` actually holds.
    Nothing is derived from a provider's name and nothing absent is
    invented -- a spec that never stated a latency produces a descriptor
    whose latency is None, which is what "not measured" has to look like.

    **Economics is the one place this deliberately says less than it
    could.** `cost_per_call == 0.0` conflates a recurring free tier, an
    installed application the founder already subscribes to, and a local
    runtime with no licence fee. A catalogue entry saying only "free" has
    not said which, so the descriptor says UNKNOWN. Only a positive cost
    is mechanically certain, and that maps to PAID.
    """
    return ProviderDescriptor(
        provider_id=spec.provider_id,
        display_name=spec.label,
        # The catalogue's own word for what kind of thing this is, taken
        # rather than re-derived: `provider_class` is an open vocabulary
        # and locality is the only classification a spec actually makes.
        provider_class=spec.locality,
        capabilities=frozenset(spec.capabilities),
        cost_per_call=spec.cost_per_call,
        is_free=spec.cost_per_call == 0.0,
        economic_class=(
            EconomicClass.PAID if spec.cost_per_call > 0.0 else EconomicClass.UNKNOWN
        ),
        economic_source=(
            "ai_infrastructure.catalog.PROVIDER_CATALOG (declared)"
        ),
        locality=spec.locality,
        privacy=spec.privacy,
        requires_network=spec.requires_network,
        requires_approval=spec.requires_approval,
        # The four facts availability() needs, carried so the projection
        # never has to read a spec again. `is_coding_agent` is the
        # catalogue guard's own verdict, normalised once here.
        inventory_key=spec.inventory_key,
        needs_credentials=spec.needs_credentials,
        is_coding_agent=is_coding_agent(spec),
        autonomous_reasoning_unsafe_reason=spec.autonomous_reasoning_unsafe_reason,
        max_context_tokens=spec.max_context_tokens,
        latency_ms=spec.latency_ms,
        declared_quality=spec.declared_quality,
        prefill_tokens_per_second=spec.prefill_tokens_per_second,
        decode_tokens_per_second=spec.decode_tokens_per_second,
        expected_itl_ms=spec.expected_itl_ms,
        supports_streaming=spec.supports_streaming,
        chars_per_token=spec.chars_per_token,
        serialises=spec.serialises,
        model_load_ms=spec.model_load_ms,
        provenance=RegistrationProvenance.DECLARED,
        notes=spec.notes,
    )


def bootstrap_registry(registry, specs=None) -> tuple[ProviderDescriptor, ...]:
    """Import the declared catalogue into the registry, idempotently.

    Safe to call on every launch: registering the same spec twice yields
    the same descriptor, and a provider whose administrative record has
    since been updated by something other than the catalogue is not
    clobbered by a re-import -- `RegistrationProvenance` is how the
    registry already distinguishes those, so a DECLARED import never
    overwrites a record that was DISCOVERED or SELF_REGISTERED.

    Returns what is now in the registry for these ids, so a caller can
    assert parity rather than trust it.
    """
    from master_agent.ai_infrastructure.catalog import PROVIDER_CATALOG

    imported: list[ProviderDescriptor] = []
    for spec in (PROVIDER_CATALOG if specs is None else specs):
        existing = registry.get(spec.provider_id)
        if existing is not None and existing.provenance is not RegistrationProvenance.DECLARED:
            # Something with better standing than a declaration already
            # owns this record. Leave it alone and report what is there.
            imported.append(existing)
            continue
        imported.append(registry.register(descriptor_for(spec)))
    return tuple(imported)


# ---- the projection, from the canonical record --------------------------
#
# Same three availability rules `availability()` has always applied, asked
# of a `ProviderDescriptor` instead of a `ProviderSpec`. Nothing is
# weakened: a coding agent is still never a reasoning provider, an unsafe
# identity is still excluded by its own recorded reason, a credentialled
# service is still unavailable until the founder configures it, and an
# inventory-backed provider is still absent until a scan says otherwise.
#
# One rule is ADDED, and only when the caller supplies the information:
# a descriptor with no currently registered executable implementation is
# unavailable. KNOWN is not EXECUTABLE, and a descriptor restored from
# last week's snapshot is not evidence that anything can be called today.

NOT_EXECUTABLE = "no executable provider implementation is registered"


def descriptor_availability(
    descriptor: Any,
    inventory: Any = None,
    enabled: frozenset[str] = frozenset(),
    executable: frozenset[str] | None = None,
) -> tuple[bool, str]:
    """Is this provider usable right now, and how do we know?

    `(available, detail)`, never a bare boolean -- "not available" and
    "not available because nothing has looked" are different facts and the
    second is the one a founder needs before installing anything.
    """
    if getattr(descriptor, "is_coding_agent", False):
        return False, CODING_AGENT_NOT_A_REASONING_PROVIDER

    unsafe = getattr(descriptor, "autonomous_reasoning_unsafe_reason", None)
    if unsafe is not None:
        return False, f"{AUTONOMOUS_REASONING_UNSAFE}: {unsafe}"

    if executable is not None and descriptor.provider_id not in executable:
        return False, NOT_EXECUTABLE

    if descriptor.needs_credentials and descriptor.provider_id not in enabled:
        return False, NO_CREDENTIALS

    if descriptor.inventory_key is None:
        return True, descriptor.notes or "configured"

    if inventory is None:
        return False, NOT_SCANNED

    application = inventory.get(descriptor.inventory_key)
    if application is None or not getattr(application, "installed", False):
        return False, NOT_INSTALLED
    if not getattr(application, "healthy", True):
        return False, NOT_HEALTHY

    version = getattr(application, "version", None)
    return True, f"{INSTALLED}{f' {version}' if version else ''}"


def profile_from_descriptor(
    descriptor: Any,
    inventory: Any = None,
    enabled: frozenset[str] | tuple[str, ...] = (),
    executable: frozenset[str] | None = None,
) -> ProviderProfile:
    """One canonical descriptor plus what the world says about it now.

    `benchmark` stays None for the same reason it always did: nothing in
    this build measures a provider, so `quality` is the declared number
    and the profile says so rather than presenting a claim as evidence.
    """
    available, detail = descriptor_availability(
        descriptor, inventory, frozenset(enabled), executable
    )
    return ProviderProfile(
        provider_id=descriptor.provider_id,
        capabilities=frozenset(descriptor.capabilities),
        locality=descriptor.locality,
        privacy=descriptor.privacy,
        quality=descriptor.declared_quality,
        benchmark=None,
        benchmark_confidence=0.0,
        cost=descriptor.cost_per_call,
        latency_ms=descriptor.latency_ms,
        available=available,
        requires_network=descriptor.requires_network,
        requires_approval=descriptor.requires_approval,
        max_context_tokens=descriptor.max_context_tokens,
        notes=detail,
        prefill_tokens_per_second=descriptor.prefill_tokens_per_second,
        decode_tokens_per_second=descriptor.decode_tokens_per_second,
        expected_itl_ms=descriptor.expected_itl_ms,
        supports_streaming=descriptor.supports_streaming,
        chars_per_token=descriptor.chars_per_token,
        serialises=descriptor.serialises,
        model_load_ms=descriptor.model_load_ms,
    )
