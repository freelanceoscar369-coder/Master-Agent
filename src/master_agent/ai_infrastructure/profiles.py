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

from master_agent.ai_infrastructure.catalog import PROVIDER_CATALOG, ProviderSpec
from master_agent.broker.profiles import ProviderProfile

#: Why a provider is not available, in a sentence a founder can act on —
#: the same discipline the Broker applies to its rejection reasons.
NOT_SCANNED = "no machine scan has run yet"
NOT_INSTALLED = "not installed on this machine"
NOT_HEALTHY = "installed but not answering"
NO_CREDENTIALS = "no credentials configured; enable it to make it selectable"
INSTALLED = "installed"


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
        specs: tuple[ProviderSpec, ...] = PROVIDER_CATALOG,
        enabled_cloud_providers: tuple[str, ...] | frozenset[str] = (),
    ) -> None:
        self._inventory_provider = inventory_provider
        self._specs = tuple(specs)
        self._enabled = frozenset(enabled_cloud_providers)

    @property
    def specs(self) -> tuple[ProviderSpec, ...]:
        return self._specs

    @property
    def enabled_cloud_providers(self) -> frozenset[str]:
        return self._enabled

    # ---- the estate ----------------------------------------------------

    def profiles(self) -> tuple[ProviderProfile, ...]:
        inventory = self._inventory()
        return tuple(profile_for(spec, inventory, self._enabled) for spec in self._specs)

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
