"""Mission Brief 032 — the AI Capability Broker, wired into Kalpavriksha.

MB031 built an engine and deliberately connected it to nothing. This suite
covers the connecting: profiles supplied from the machine, decisions
recorded against tasks, paid selections routed to the founder, free ones
running immediately, replay from what was stored rather than from today's
policy, and a Model Router with no opinion of its own left.

The posture is MB031's: **the forbidden things are asserted, not trusted**.
No vendor name outside the one catalogue file, no ranking outside the
Broker, no execution surface in the wiring layer, and no import that would
drag Mission Control into the Brain.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from master_agent.ai_infrastructure import catalog, tiers
from master_agent.ai_infrastructure.approval import (
    PAID,
    PAID_CAPABILITY,
    RISK_TIER,
    SENSITIVE_CAPABILITY,
    SENSITIVE_THIRD_PARTY,
    ProviderApprovalGate,
    approval_needed,
    describe_impact,
)
from master_agent.ai_infrastructure.ledger import (
    DENIED,
    GRANTED,
    NOT_REQUIRED,
    PENDING,
    DecisionEntry,
    DecisionLedger,
    InMemoryDecisionStore,
    JsonFileDecisionStore,
    LedgerError,
    UnknownDecision,
)
from master_agent.ai_infrastructure.profiles import (
    NO_CREDENTIALS,
    NOT_HEALTHY,
    NOT_INSTALLED,
    NOT_SCANNED,
    ProviderSource,
    availability,
    profile_for,
)
from master_agent.ai_infrastructure.refusal import (
    APPROVAL_DENIED,
    APPROVAL_PENDING,
    NO_PROVIDER,
    BrokerRefusal,
    NoProviderAvailable,
    ProviderApprovalDenied,
    ProviderApprovalPending,
    refusal_from_decision,
)
from master_agent.ai_infrastructure.service import (
    DEFAULT_CAPABILITY,
    AiCapabilityService,
    Selection,
    SelectionOutcome,
)
from master_agent.broker.decision import (
    BELOW_FLOOR,
    EXCLUDED,
    NEEDS_NETWORK,
    NO_PROVIDER_AVAILABLE,
    NOT_PRIVATE,
    SELECTED,
    UNAVAILABLE,
)
from master_agent.broker.policy import BEST_QUALITY, LOWEST_COST, PREFER_LOCAL, PRIVACY_FIRST
from master_agent.broker.profiles import ProviderProfile
from master_agent.desktop.catalog import BY_KEY as DESKTOP_BY_KEY
from master_agent.mission_control.events import EventType
from master_agent.permissions.permission_system import GrantScope
from master_agent.plugins.base import Plugin, PluginManifest, RiskTier
from master_agent.plugins.model_router import (
    NO_SELECTOR,
    REASONING,
    BrokerUnavailable,
    ModelRouter,
    ProviderNotWired,
    ProviderSelector,
    RoutingContext,
    SelectionRequest,
)
from master_agent.plugins.registry import PluginRegistry
from tests.broker_test_support import (
    CLOUD_BEST,
    CLOUD_CHEAP,
    DESKTOP_SUB,
    ESTATE,
    LOCAL_FREE,
    LOCAL_WEAK,
    Harness,
    RecordingProvider,
    application,
    inventory,
    source,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = REPO_ROOT / "src" / "master_agent" / "ai_infrastructure"
ROUTER = REPO_ROOT / "src" / "master_agent" / "plugins" / "model_router.py"
MODULES = sorted(PACKAGE_DIR.glob("*.py"))

ALL_INSTALLED = ("alpha_runtime", "beta_runtime", "gamma_app")
BOTH_CLOUDS = ("delta-cloud", "epsilon-cloud")


def rejections(decision) -> dict[str, str]:
    """`{provider_id: why it was rejected}` off a `BrokerDecision`."""
    return {candidate.provider_id: candidate.reason for candidate in decision.rejected}


def test_the_invented_estate_spans_every_axis_the_broker_filters_on():
    """This suite's conclusions are only worth anything if the estate it
    decides over actually varies: a fixture where everything is free and
    local would pass every test here and prove nothing."""
    assert {s.locality for s in ESTATE} == {"local", "desktop", "cloud"}
    assert {s.privacy for s in ESTATE} == {"private", "third_party"}
    assert {s.cost_per_call > 0 for s in ESTATE} == {True, False}
    assert {s.needs_credentials for s in ESTATE} == {True, False}
    assert LOCAL_WEAK.declared_quality < LOCAL_FREE.declared_quality < DESKTOP_SUB.declared_quality
    assert CLOUD_CHEAP.cost_per_call < CLOUD_BEST.cost_per_call


def test_a_recorded_decision_is_a_ledger_entry():
    harness = Harness("alpha_runtime")
    harness.decide()

    assert isinstance(harness.ledger.last(), DecisionEntry)


def test_a_successful_outcome_carries_a_selection():
    assert isinstance(Harness("alpha_runtime").decide().selection, Selection)


def test_an_in_memory_store_keeps_a_ledger_off_disk():
    """Proof that nothing above the store assumes a filesystem — the same
    property `InMemoryStateStore` gives persistence."""
    store = InMemoryDecisionStore()
    harness = Harness("alpha_runtime", store=store)

    harness.decide()

    assert len(store.rows) == 1


# =========================================================================
# Tiers — the founder-facing reading of two numbers (Deliverable 9)
# =========================================================================


@pytest.mark.parametrize(
    ("cost", "expected"),
    [
        (0.0, tiers.FREE),
        (-1.0, tiers.FREE),
        (0.001, tiers.LOW),
        (0.01, tiers.LOW),
        (0.011, tiers.MODERATE),
        (0.10, tiers.MODERATE),
        (0.11, tiers.HIGH),
        (5.0, tiers.HIGH),
    ],
)
def test_cost_tier_reads_a_number(cost, expected):
    assert tiers.cost_tier(cost) == expected


def test_an_unrecorded_cost_is_unknown_rather_than_free():
    """ADR-0016's rule: 0 and "we do not know" are different facts, and
    calling the second one free is how a founder gets surprised."""
    assert tiers.cost_tier(None) == tiers.UNKNOWN
    assert tiers.is_free(None) is False


@pytest.mark.parametrize(
    ("quality", "expected"),
    [
        (0.0, tiers.BASIC),
        (0.59, tiers.BASIC),
        (0.60, tiers.FAIR),
        (0.74, tiers.FAIR),
        (0.75, tiers.GOOD),
        (0.87, tiers.GOOD),
        (0.88, tiers.STRONG),
        (1.0, tiers.STRONG),
    ],
)
def test_quality_tier_reads_a_number(quality, expected):
    assert tiers.quality_tier(quality) == expected


def test_an_unrecorded_quality_is_unknown():
    assert tiers.quality_tier(None) == tiers.UNKNOWN


@pytest.mark.parametrize(
    ("benchmark", "expected"), [(None, tiers.DECLARED), (0.8, tiers.MEASURED)]
)
def test_quality_basis_says_where_the_number_came_from(benchmark, expected):
    """ADR-0017 Decision 5. A declared number and a measured one rank the
    same way and mean very different things."""
    assert tiers.quality_basis(benchmark) == expected


@pytest.mark.parametrize("cost", [0.0, -0.5])
def test_free_is_free(cost):
    assert tiers.is_free(cost) is True


@pytest.mark.parametrize("cost", [0.0001, 1.0])
def test_anything_above_zero_is_not_free(cost):
    assert tiers.is_free(cost) is False


def test_describe_cost_names_the_tier_and_the_number():
    """The tier alone hides an order of magnitude; the number alone means
    nothing to someone reading fast."""
    assert tiers.describe_cost(0.0) == tiers.FREE
    assert tiers.describe_cost(None) == tiers.UNKNOWN
    assert tiers.describe_cost(0.005) == "low (0.0050 per call)"
    assert tiers.describe_cost(0.5) == "high (0.5000 per call)"


def test_describe_quality_carries_its_basis():
    assert tiers.describe_quality(0.72, None) == "fair (0.72, declared)"
    assert tiers.describe_quality(0.91, 0.91) == "strong (0.91, measured)"
    assert tiers.describe_quality(None, None) == tiers.UNKNOWN


# =========================================================================
# The provider catalogue — the one file allowed to name a product
# =========================================================================


def test_the_catalogue_is_not_empty():
    assert catalog.PROVIDER_CATALOG


def test_every_provider_id_is_unique():
    ids = [spec.provider_id for spec in catalog.PROVIDER_CATALOG]
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize("spec", catalog.PROVIDER_CATALOG, ids=lambda s: s.provider_id)
def test_every_spec_states_where_its_numbers_came_from(spec):
    """Every quality number in this build is a guess. A guess presented
    without saying so is a measurement as far as the reader is concerned."""
    assert spec.basis, f"{spec.provider_id} declares a quality with no stated basis"


@pytest.mark.parametrize("spec", catalog.PROVIDER_CATALOG, ids=lambda s: s.provider_id)
def test_every_declared_quality_is_a_probability(spec):
    assert 0.0 <= spec.declared_quality <= 1.0


@pytest.mark.parametrize("spec", catalog.PROVIDER_CATALOG, ids=lambda s: s.provider_id)
def test_no_provider_costs_a_negative_amount(spec):
    assert spec.cost_per_call >= 0.0


@pytest.mark.parametrize("spec", catalog.PROVIDER_CATALOG, ids=lambda s: s.provider_id)
def test_every_locality_is_one_the_broker_understands(spec):
    from master_agent.broker.profiles import LOCALITIES

    assert spec.locality in LOCALITIES


@pytest.mark.parametrize("spec", catalog.PROVIDER_CATALOG, ids=lambda s: s.provider_id)
def test_every_privacy_class_is_one_the_broker_understands(spec):
    from master_agent.broker.profiles import PRIVATE, THIRD_PARTY

    assert spec.privacy in (PRIVATE, THIRD_PARTY)


@pytest.mark.parametrize("spec", catalog.PROVIDER_CATALOG, ids=lambda s: s.provider_id)
def test_every_spec_offers_at_least_one_capability(spec):
    assert spec.capabilities


LOCAL_SPECS = [s for s in catalog.PROVIDER_CATALOG if s.locality == catalog.LOCAL]
CLOUD_SPECS = [s for s in catalog.PROVIDER_CATALOG if s.locality == catalog.CLOUD]


@pytest.mark.parametrize("spec", LOCAL_SPECS, ids=lambda s: s.provider_id)
def test_a_local_provider_is_private_and_needs_no_network(spec):
    """Local means on this machine. A "local" provider that phones home is
    a contradiction the privacy filter would silently get wrong."""
    assert spec.privacy == catalog.PRIVATE
    assert spec.requires_network is False


@pytest.mark.parametrize("spec", CLOUD_SPECS, ids=lambda s: s.provider_id)
def test_a_cloud_provider_needs_the_network(spec):
    assert spec.requires_network is True


def test_the_catalogue_spans_local_and_remote():
    """Both branches above are worth having only if both are populated --
    a parametrised test over an empty list passes silently."""
    assert LOCAL_SPECS
    assert CLOUD_SPECS


@pytest.mark.parametrize("spec", catalog.PROVIDER_CATALOG, ids=lambda s: s.provider_id)
def test_a_spec_is_found_by_the_machine_or_by_configuration_never_both(spec):
    assert not (spec.inventory_key and spec.needs_credentials)


@pytest.mark.parametrize(
    "spec", catalog.inventory_backed(), ids=lambda s: s.provider_id
)
def test_every_inventory_key_exists_in_the_desktop_catalogue(spec):
    """The join MB032 Deliverable 3 depends on. A typo here is a provider
    that is silently never available, which is the hardest kind of bug to
    notice — everything works, it is just quieter."""
    assert spec.inventory_key in DESKTOP_BY_KEY


def test_every_paid_provider_needs_credentials():
    """Nothing should be able to spend money on a machine that was never
    configured to."""
    for spec in catalog.PROVIDER_CATALOG:
        if spec.cost_per_call > 0:
            assert spec.needs_credentials, f"{spec.provider_id} can spend without setup"


def test_find_resolves_a_provider_id():
    assert catalog.find("ollama.local") is not None
    assert catalog.find("  ollama.local  ") is not None
    assert catalog.find("nothing-like-this") is None
    assert catalog.find("") is None


def test_credentialled_and_inventory_backed_partition_the_catalogue():
    both = set(catalog.inventory_backed()) | set(catalog.credentialled())
    assert both == set(catalog.PROVIDER_CATALOG)


def test_the_shipped_catalogue_offers_reasoning():
    """The Brain's door needs at least one thing behind it, or the whole
    wiring is decorative."""
    assert any(catalog.REASONING in spec.capabilities for spec in catalog.PROVIDER_CATALOG)


# =========================================================================
# Profiles from the machine (Deliverable 3)
# =========================================================================


def test_no_scan_means_a_local_provider_is_not_available():
    """"Nothing has looked" is not "it is installed". Assuming presence is
    how a selection succeeds and the call fails ten seconds later."""
    available, detail = availability(LOCAL_FREE, inventory=None)

    assert available is False
    assert detail == NOT_SCANNED


def test_an_installed_provider_is_available_and_says_its_version():
    available, detail = availability(LOCAL_FREE, inventory("alpha_runtime"))

    assert available is True
    assert "installed" in detail
    assert "1.0" in detail


def test_a_missing_provider_says_it_is_not_installed():
    available, detail = availability(LOCAL_FREE, inventory("beta_runtime"))

    assert available is False
    assert detail == NOT_INSTALLED


def test_a_present_but_broken_provider_is_distinguished_from_a_missing_one():
    """Two different answers for the founder: install it, or fix it."""
    machine = inventory("alpha_runtime", alpha_runtime=False)
    available, detail = availability(LOCAL_FREE, machine)

    assert available is False
    assert detail == NOT_HEALTHY


def test_a_credentialled_provider_is_unavailable_until_it_is_enabled():
    available, detail = availability(CLOUD_CHEAP, inventory(), frozenset())

    assert available is False
    assert detail == NO_CREDENTIALS


def test_an_enabled_credentialled_provider_is_available():
    available, _ = availability(CLOUD_CHEAP, inventory(), frozenset({"delta-cloud"}))

    assert available is True


def test_an_installed_application_with_no_version_still_reads_as_installed():
    machine = inventory()
    machine = type(machine)(
        applications=[application("alpha_runtime", version=None)],
        processes=[],
        platform="test",
        captured_at=machine.captured_at,
    )
    available, detail = availability(LOCAL_FREE, machine)

    assert available is True
    assert detail == "installed"


def test_a_profile_is_never_marked_as_benchmarked():
    """Nothing in this build measures a provider, so nothing may claim it
    did (ADR-0017 Decision 5)."""
    profile = profile_for(LOCAL_FREE, inventory("alpha_runtime"))

    assert profile.benchmark is None
    assert profile.benchmark_confidence == 0.0
    assert profile.effective_quality == LOCAL_FREE.declared_quality


@pytest.mark.parametrize(
    ("field", "expected"),
    [
        ("provider_id", "alpha-local"),
        ("locality", "local"),
        ("privacy", "private"),
        ("quality", 0.75),
        ("cost", 0.0),
        ("latency_ms", 4000.0),
        ("requires_network", False),
        ("max_context_tokens", 32_768),
        ("requires_approval", False),
    ],
)
def test_a_spec_maps_onto_a_broker_profile(field, expected):
    profile = profile_for(LOCAL_FREE, inventory("alpha_runtime"))

    assert getattr(profile, field) == expected


def test_capabilities_survive_the_translation():
    profile = profile_for(LOCAL_FREE, inventory("alpha_runtime"))

    assert profile.serves("reasoning")
    assert profile.serves("coding")
    assert not profile.serves("vision")


def test_the_source_builds_one_profile_per_spec():
    assert len(source(*ALL_INSTALLED).profiles()) == len(ESTATE)


def test_the_source_counts_what_is_available():
    assert source("alpha_runtime").counts() == (1, 5)
    assert source(*ALL_INSTALLED).counts() == (3, 5)
    assert source(*ALL_INSTALLED, enabled=BOTH_CLOUDS).counts() == (5, 5)


def test_the_source_reports_whether_anything_has_been_scanned():
    assert source("alpha_runtime").has_scan() is True
    assert source(scanned=False).has_scan() is False


def test_an_unscanned_machine_offers_nothing_local():
    assert source(scanned=False).counts() == (0, 5)


def test_a_scan_that_raises_is_treated_as_no_scan():
    """A failed read is absent data, never an exception thrown at whoever
    asked for a provider — the tolerance `DashboardSources` already
    applies to every read it makes."""

    def explode():
        raise OSError("inventory unreadable")

    unlucky = ProviderSource(inventory_provider=explode, specs=ESTATE)

    assert unlucky.has_scan() is False
    assert unlucky.counts() == (0, 5)


def test_the_estate_is_rebuilt_on_every_call_so_a_new_scan_is_seen():
    """A cached estate is how a system confidently refuses work it could
    now do."""
    machine: list = [None]
    live = ProviderSource(inventory_provider=lambda: machine[0], specs=ESTATE)

    assert live.counts() == (0, 5)
    machine[0] = inventory(*ALL_INSTALLED)
    assert live.counts() == (3, 5)


def test_the_source_preserves_catalogue_order_and_does_not_rank():
    """A list is not a ranking — the same property MB030 asserts of the
    desktop catalogue, for the same reason."""
    ids = [profile.provider_id for profile in source(*ALL_INSTALLED).profiles()]

    assert ids == [spec.provider_id for spec in ESTATE]


def test_available_returns_only_what_can_be_used():
    available = source("alpha_runtime").available()

    assert [p.provider_id for p in available] == ["alpha-local"]


def test_profiles_are_frozen_so_a_caller_cannot_edit_the_estate():
    from dataclasses import FrozenInstanceError

    profile = source("alpha_runtime").profiles()[0]
    with pytest.raises(FrozenInstanceError):
        profile.available = True  # type: ignore[misc]


# =========================================================================
# The decision ledger (Deliverables 7 and 8)
# =========================================================================


def test_every_decision_reaches_the_ledger():
    harness = Harness("alpha_runtime")

    harness.decide()

    assert len(harness.ledger) == 1


def test_a_refusal_is_recorded_as_carefully_as_a_selection():
    """A decision nobody recorded cannot be replayed, and a refusal is
    exactly the decision a founder asks about later."""
    harness = Harness(scanned=False)

    outcome = harness.decide()

    assert outcome.ok is False
    assert len(harness.ledger) == 1
    assert harness.ledger.last().outcome == NO_PROVIDER_AVAILABLE


def test_entry_ids_start_at_one_and_increment():
    harness = Harness("alpha_runtime")

    for index in range(1, 4):
        harness.decide(task_id=f"t{index}")
        assert harness.ledger.last().entry_id == index


@pytest.mark.parametrize(
    ("field", "expected"),
    [
        ("task_id", "t1"),
        ("capability", "reasoning"),
        ("outcome", SELECTED),
        ("provider_id", "alpha-local"),
        ("policy_version", "balanced/1"),
        ("cost", 0.0),
        ("quality", 0.75),
        ("cost_tier", tiers.FREE),
        ("quality_tier", tiers.GOOD),
        ("quality_basis", tiers.DECLARED),
        ("approval_state", NOT_REQUIRED),
    ],
)
def test_a_ledger_entry_carries_what_a_founder_asks(field, expected):
    harness = Harness("alpha_runtime")
    harness.decide()

    assert getattr(harness.ledger.last(), field) == expected


def test_a_refused_entry_has_no_provider_and_no_tiers():
    harness = Harness(scanned=False)
    harness.decide()
    entry = harness.ledger.last()

    assert entry.provider_id is None
    assert entry.cost_tier == tiers.UNKNOWN
    assert entry.quality_tier == tiers.UNKNOWN
    assert entry.selected is False


def test_a_selected_free_decision_is_immediately_executable():
    harness = Harness("alpha_runtime")
    harness.decide()

    assert harness.ledger.last().executable is True


def test_a_pending_decision_is_not_executable():
    harness = Harness(enabled=BOTH_CLOUDS)
    harness.decide()

    assert harness.ledger.last().executable is False


def test_the_ledger_finds_the_most_recent_decision_for_a_task():
    harness = Harness("alpha_runtime")
    harness.decide(task_id="repeated")
    harness.decide(task_id="repeated")

    assert harness.ledger.for_task("repeated").entry_id == 2
    assert len(harness.ledger.all_for_task("repeated")) == 2


def test_an_unknown_task_has_no_entry():
    assert Harness("alpha_runtime").ledger.for_task("never-asked") is None


def test_recent_decisions_are_newest_first():
    harness = Harness("alpha_runtime")
    for index in range(4):
        harness.decide(task_id=f"t{index}")

    assert [e.task_id for e in harness.ledger.recent(2)] == ["t3", "t2"]


def test_recent_of_nothing_is_nothing():
    assert Harness("alpha_runtime").ledger.recent(0) == ()


def test_the_ledger_hands_back_copies():
    """Evidence a caller can edit is not evidence."""
    harness = Harness("alpha_runtime")
    harness.decide()
    entries = harness.ledger.entries()
    entries_again = harness.ledger.entries()

    assert entries == entries_again
    assert entries is not entries_again


def test_setting_an_unknown_approval_state_is_refused():
    harness = Harness("alpha_runtime")
    harness.decide()

    with pytest.raises(LedgerError):
        harness.ledger.set_approval(1, "maybe")


def test_annotating_an_unknown_decision_is_refused():
    with pytest.raises(UnknownDecision):
        Harness("alpha_runtime").ledger.set_approval(99, GRANTED)


def test_annotating_approval_never_touches_the_record():
    harness = Harness("alpha_runtime")
    harness.decide()
    before = harness.ledger.get(1).record

    after = harness.ledger.set_approval(1, GRANTED, "abc123")

    assert after.record is before
    assert after.approval_state == GRANTED
    assert after.approval_id == "abc123"


def test_annotating_without_an_id_keeps_the_one_already_there():
    harness = Harness("alpha_runtime")
    harness.decide()
    harness.ledger.set_approval(1, PENDING, "abc123")

    assert harness.ledger.set_approval(1, GRANTED).approval_id == "abc123"


def test_awaiting_approval_lists_only_what_is_still_open():
    harness = Harness(enabled=BOTH_CLOUDS)
    harness.decide(task_id="paid")

    assert [e.task_id for e in harness.ledger.awaiting_approval()] == ["paid"]


def test_a_ledger_round_trips_through_plain_data():
    harness = Harness("alpha_runtime")
    harness.decide()
    harness.decide(task_id="t2")

    rebuilt = DecisionLedger()
    assert rebuilt.restore(harness.ledger.as_dicts()) == 2
    assert rebuilt.entries() == harness.ledger.entries()


def test_restoring_the_same_entry_twice_adds_it_once():
    harness = Harness("alpha_runtime")
    harness.decide()
    rows = harness.ledger.as_dicts()

    rebuilt = DecisionLedger()
    rebuilt.restore(rows)
    assert rebuilt.restore(rows) == 0
    assert len(rebuilt) == 1


def test_one_unreadable_row_does_not_cost_the_rest_of_the_history():
    """The same tolerance the event log applies to a truncated final
    line: history is worth more than tidiness."""
    harness = Harness("alpha_runtime")
    harness.decide()
    rows = [{"nonsense": True}, *harness.ledger.as_dicts()]

    rebuilt = DecisionLedger()

    assert rebuilt.restore(rows) == 1


def test_restored_entries_are_ordered_by_id():
    harness = Harness("alpha_runtime")
    for index in range(3):
        harness.decide(task_id=f"t{index}")

    rebuilt = DecisionLedger()
    rebuilt.restore(list(reversed(harness.ledger.as_dicts())))

    assert [e.entry_id for e in rebuilt.entries()] == [1, 2, 3]


def test_the_next_id_continues_after_a_restore():
    harness = Harness("alpha_runtime")
    harness.decide()
    rebuilt = DecisionLedger()
    rebuilt.restore(harness.ledger.as_dicts())

    rebuilt.record(harness.ledger.get(1).record)

    assert rebuilt.last().entry_id == 2


def test_a_json_store_round_trips(tmp_path):
    store = JsonFileDecisionStore(tmp_path / "nested" / "decisions.json")
    harness = Harness("alpha_runtime", store=store)
    harness.decide()

    assert store.path.exists()
    assert DecisionLedger(store=store).load() == 1


def test_a_missing_store_file_reads_as_no_history(tmp_path):
    assert JsonFileDecisionStore(tmp_path / "absent.json").read() == []


def test_a_store_file_that_is_not_a_list_reads_as_no_history(tmp_path):
    path = tmp_path / "decisions.json"
    path.write_text('{"not": "a list"}', encoding="utf-8")

    assert JsonFileDecisionStore(path).read() == []


def test_a_store_file_skips_rows_that_are_not_objects(tmp_path):
    path = tmp_path / "decisions.json"
    path.write_text(json.dumps([1, "two", {"entry_id": 3}]), encoding="utf-8")

    assert JsonFileDecisionStore(path).read() == [{"entry_id": 3}]


def test_a_broken_store_never_turns_a_decision_into_a_refusal():
    """A broken disk is a recording problem. Refusing an AI task over it
    would be the tail wagging the dog."""

    class Broken:
        def read(self):
            raise OSError("no")

        def write(self, _rows):
            raise OSError("disk full")

    harness = Harness("alpha_runtime", store=Broken())

    outcome = harness.decide()

    assert outcome.ok is True
    assert harness.ledger.write_failures


def test_a_store_that_cannot_be_read_loads_nothing_and_says_so():
    class Unreadable:
        def read(self):
            raise OSError("gone")

        def write(self, _rows):
            return None

    ledger = DecisionLedger(store=Unreadable())

    assert ledger.load() == 0
    assert ledger.write_failures


def test_a_ledger_with_no_store_still_records():
    ledger = DecisionLedger()
    harness = Harness("alpha_runtime")
    harness.decide()

    ledger.restore(harness.ledger.as_dicts())

    assert ledger.load() == 0
    assert len(ledger) == 1


# ---- replay (Deliverable 8) ---------------------------------------------


def test_a_stored_decision_replays_to_the_same_answer():
    harness = Harness(*ALL_INSTALLED)
    harness.decide()

    assert harness.ledger.replay_matches(1) is True


def test_replay_reproduces_the_winner():
    harness = Harness(*ALL_INSTALLED)
    harness.decide()

    assert harness.ledger.replay(1).winner == harness.ledger.get(1).provider_id


def test_replay_reproduces_the_whole_ranking_not_just_the_winner():
    harness = Harness(*ALL_INSTALLED, enabled=BOTH_CLOUDS)
    harness.decide()
    original = harness.ledger.get(1).record.decision

    fresh = harness.ledger.replay(1)

    assert [c.provider_id for c in fresh.ranked] == [
        c.provider_id for c in original.ranked
    ]


def test_replay_uses_the_stored_policy_not_the_current_one():
    """The load-bearing property of Deliverable 8. Replaying against
    today's policy would not be reproducing history — it would be making a
    new decision and calling it history."""
    harness = Harness(*ALL_INSTALLED, enabled=BOTH_CLOUDS)
    harness.decide()
    under_balanced = harness.ledger.get(1).provider_id

    harness.broker.use_policy(BEST_QUALITY)

    assert harness.ledger.replay(1).winner == under_balanced
    assert harness.ledger.replay_matches(1) is True


def test_replay_uses_the_stored_providers_not_the_current_estate():
    """The machine changes. A record that re-read the estate would answer
    a different question every time it was asked."""
    machine = [inventory(*ALL_INSTALLED)]
    harness = Harness(*ALL_INSTALLED)
    harness.providers = ProviderSource(
        inventory_provider=lambda: machine[0], specs=ESTATE
    )
    harness.service._providers = harness.providers
    harness.decide()
    chosen = harness.ledger.get(1).provider_id

    machine[0] = inventory()  # everything uninstalled since

    assert harness.ledger.replay(1).winner == chosen


def test_replay_does_not_append_to_the_ledger():
    """Replaying history must not change it."""
    harness = Harness("alpha_runtime")
    harness.decide()

    harness.ledger.replay(1)
    harness.ledger.replay_matches(1)

    assert len(harness.ledger) == 1


def test_replay_of_an_unknown_decision_is_refused():
    with pytest.raises(UnknownDecision):
        Harness("alpha_runtime").ledger.replay(42)


def test_a_decision_stored_without_its_record_says_it_cannot_be_replayed():
    """Rather than replaying something else and calling it the same."""
    harness = Harness("alpha_runtime")
    harness.decide()
    rows = harness.ledger.as_dicts()
    rows[0]["record"] = None

    rebuilt = DecisionLedger()
    rebuilt.restore(rows)

    with pytest.raises(UnknownDecision):
        rebuilt.replay(1)


def test_every_stored_decision_replays():
    harness = Harness(*ALL_INSTALLED, enabled=BOTH_CLOUDS)
    harness.decide(task_id="a")
    harness.decide(task_id="b", sensitive=True)
    harness.decide(task_id="c", offline=True)
    harness.decide(task_id="d", min_quality=0.99)

    assert set(harness.ledger.replay_all().values()) == {True}


def test_a_decision_replays_after_a_round_trip_through_storage(tmp_path):
    """Deterministic replay has to survive the process, or it is a
    property of one run rather than of the record."""
    store = JsonFileDecisionStore(tmp_path / "decisions.json")
    first = Harness(*ALL_INSTALLED, enabled=BOTH_CLOUDS, store=store)
    first.decide()
    winner = first.ledger.get(1).provider_id

    reloaded = DecisionLedger(store=JsonFileDecisionStore(tmp_path / "decisions.json"))
    reloaded.load()

    assert reloaded.replay_matches(1) is True
    assert reloaded.replay(1).winner == winner


def test_a_replayed_digest_matches_the_stored_one():
    harness = Harness(*ALL_INSTALLED)
    harness.decide()
    stored = harness.ledger.get(1).inputs_digest

    assert harness.ledger.replay(1).inputs_digest == stored


def test_entry_for_decision_matches_by_identity_not_by_value():
    """Two identical decisions are two decisions. Matching by value would
    let a caller reconcile with the wrong one."""
    harness = Harness("alpha_runtime")
    harness.decide(task_id="same")
    first = harness.ledger.get(1).record.decision
    harness.decide(task_id="same")

    assert harness.ledger.entry_for_decision(first).entry_id == 1


def test_entry_for_an_unknown_decision_is_none():
    harness = Harness("alpha_runtime")
    other = Harness("alpha_runtime")
    other.decide()

    assert harness.ledger.entry_for_decision(
        other.ledger.get(1).record.decision
    ) is None


# =========================================================================
# The approval rule, and the queue it routes to (Deliverables 5 and 6)
# =========================================================================


def profile(**kwargs) -> ProviderProfile:
    defaults = {
        "provider_id": "p",
        "cost": 0.0,
        "privacy": "private",
        "locality": "local",
    }
    defaults.update(kwargs)
    return ProviderProfile(**defaults)


def test_a_free_private_provider_needs_no_approval():
    assert approval_needed(profile(), "unrestricted") is None


def test_a_paid_provider_needs_approval():
    assert approval_needed(profile(cost=0.01), "unrestricted") == PAID


def test_sensitive_work_reaching_a_third_party_needs_approval():
    """ADR-0017 Decision 7's deliberate addition: a *free* cloud model is
    still a third party receiving the founder's data."""
    third_party = profile(privacy="third_party", locality="cloud")

    assert approval_needed(third_party, "sensitive") == SENSITIVE_THIRD_PARTY


def test_sensitive_work_staying_on_the_machine_needs_no_approval():
    assert approval_needed(profile(), "sensitive") is None


def test_a_free_third_party_provider_on_unrestricted_work_needs_no_approval():
    assert approval_needed(profile(privacy="third_party"), "unrestricted") is None


def test_a_paid_sensitive_selection_is_reported_as_paid():
    """One question, not two. The founder is being asked to authorise one
    call and should be asked once."""
    paid = profile(cost=0.5, privacy="third_party")

    assert approval_needed(paid, "sensitive") == PAID


def test_a_provider_with_no_cost_recorded_needs_approval():
    """Unknown is not free (see `tiers.is_free`), so an unpriced provider
    is gated rather than waved through."""
    assert approval_needed(profile(cost=None), "unrestricted") == PAID


def test_the_first_paid_request_asks_the_founder():
    harness = Harness(enabled=BOTH_CLOUDS)

    outcome = harness.decide()

    assert outcome.ok is False
    assert outcome.refusal.kind == APPROVAL_PENDING
    assert len(harness.mission_control.approvals.open()) == 1


def test_asking_twice_asks_the_founder_once():
    """The Runtime re-offers a held task every cycle; without idempotency
    a five-second wait would be five hundred identical questions."""
    harness = Harness(enabled=BOTH_CLOUDS)

    harness.decide()
    harness.decide()

    assert len(harness.mission_control.approvals.open()) == 1


def test_the_pending_refusal_names_the_approval_the_founder_must_answer():
    harness = Harness(enabled=BOTH_CLOUDS)

    outcome = harness.decide()
    open_approval = harness.mission_control.approvals.open()[0]

    assert outcome.refusal.approval_id == open_approval.approval_id


def test_an_approved_provider_becomes_selectable():
    harness = Harness(enabled=BOTH_CLOUDS)
    harness.decide()

    harness.approve_everything()
    outcome = harness.decide()

    assert outcome.ok is True
    assert outcome.selection.provider_id == "delta-cloud"
    assert outcome.selection.approval_state == GRANTED


def test_a_rejected_provider_is_refused_and_not_retried():
    harness = Harness(enabled=BOTH_CLOUDS)
    harness.decide()

    harness.reject_everything()
    outcome = harness.decide()

    assert outcome.refusal.kind == APPROVAL_DENIED
    assert "rejected" in outcome.refusal.reason


def test_an_expired_request_is_refused_with_its_own_reason():
    harness = Harness(enabled=BOTH_CLOUDS)
    harness.decide()
    approval = harness.mission_control.approvals.open()[0]
    harness.mission_control.approvals.expire(approval.approval_id)

    outcome = harness.decide()

    assert outcome.refusal.kind == APPROVAL_DENIED
    assert "expired" in outcome.refusal.reason


def test_the_queue_entry_is_classified_irreversible():
    """Spent money cannot be unspent. Classifying it anywhere softer would
    forfeit ADR-0009's guarantee about standing grants."""
    harness = Harness(enabled=BOTH_CLOUDS)
    harness.decide()

    assert harness.mission_control.approvals.open()[0].risk_tier == RISK_TIER.value
    assert RISK_TIER is RiskTier.IRREVERSIBLE


def test_a_standing_grant_can_never_authorise_a_paid_call():
    """ADR-0009, inherited rather than reimplemented: an
    `ALWAYS_FOR_CAPABILITY` grant never satisfies an `IRREVERSIBLE`
    check, so "yes, use paid AI" can never become "yes, forever"."""
    harness = Harness(enabled=BOTH_CLOUDS)
    harness.permissions.grant(
        "delta-cloud", PAID_CAPABILITY, GrantScope.ALWAYS_FOR_CAPABILITY
    )

    outcome = harness.decide()

    assert outcome.refusal.kind == APPROVAL_PENDING


def test_a_once_grant_authorises_exactly_one_call():
    harness = Harness(enabled=BOTH_CLOUDS)
    harness.permissions.grant("delta-cloud", PAID_CAPABILITY, GrantScope.ONCE)

    first = harness.decide(task_id="one")
    second = harness.decide(task_id="two")

    assert first.ok is True
    assert second.ok is False


def test_the_queue_entry_names_the_provider_as_the_executive():
    harness = Harness(enabled=BOTH_CLOUDS)
    harness.decide()

    assert harness.mission_control.approvals.open()[0].executive_id == "delta-cloud"


def test_two_providers_for_one_task_are_two_separate_questions():
    """The capability key carries the provider, so approving one does not
    silently approve the other."""
    gate = ProviderApprovalGate(Harness().mission_control, Harness().permissions)

    first = gate.qualified_capability(PAID, "delta-cloud")
    second = gate.qualified_capability(PAID, "epsilon-cloud")

    assert first != second
    assert "delta-cloud" in first


def test_the_two_reasons_produce_two_different_questions():
    harness = Harness()
    gate = ProviderApprovalGate(harness.mission_control, harness.permissions)

    assert gate.qualified_capability(PAID, "x") != gate.qualified_capability(
        SENSITIVE_THIRD_PARTY, "x"
    )


def test_the_request_is_attributed_to_the_broker():
    harness = Harness(enabled=BOTH_CLOUDS)
    harness.decide()

    assert (
        harness.mission_control.approvals.open()[0].requested_by
        == "ai_capability_broker"
    )


def test_asking_the_founder_publishes_the_events_they_already_watch_for():
    """Zero new approval paths (ADR-0018 Decision 3) means zero new event
    types: anything already listening for "you are being asked" keeps
    working."""
    harness = Harness(enabled=BOTH_CLOUDS)
    seen = []
    harness.mission_control.bus.subscribe(lambda event: seen.append(event.event_type))

    harness.decide()

    assert EventType.APPROVAL_REQUESTED in seen
    assert EventType.APPROVAL_REQUIRED in seen


def test_the_impact_of_a_paid_call_names_the_money():
    impact = describe_impact("delta-cloud", PAID, "reasoning", 0.005, "cloud", "third_party")

    assert "delta-cloud" in impact
    assert "0.0050 per call" in impact
    assert "spends money" in impact


def test_the_impact_of_a_sensitive_call_names_the_disclosure():
    impact = describe_impact(
        "delta-cloud", SENSITIVE_THIRD_PARTY, "reasoning", 0.0, "cloud", "third_party"
    )

    assert "sensitive" in impact
    assert "cannot be recalled" in impact


def test_an_approval_carries_the_objective_it_belongs_to():
    from master_agent.mission_control.tasks import Objective

    harness = Harness(enabled=BOTH_CLOUDS)
    objective = harness.mission_control.submit_objective(
        Objective(description="Write the quarterly summary", tasks=[])
    )

    harness.decide(objective_id=objective.objective_id)
    approval = harness.mission_control.approvals.open()[0]

    assert approval.objective_id == objective.objective_id
    assert approval.objective == "Write the quarterly summary"


def test_an_unknown_objective_is_not_a_reason_to_refuse():
    harness = Harness(enabled=BOTH_CLOUDS)

    harness.decide(objective_id="no-such-objective")

    assert harness.mission_control.approvals.open()[0].objective is None


def test_a_service_with_no_approval_queue_refuses_to_spend():
    """Fail closed. A paid selection with nowhere to ask is not
    authorised, it is unanswerable."""
    harness = Harness(enabled=BOTH_CLOUDS, with_approvals=False)

    outcome = harness.decide()

    assert outcome.refusal.kind == APPROVAL_DENIED
    assert "refusing rather than spending" in outcome.refusal.reason
    assert harness.ledger.last().approval_state == DENIED


# =========================================================================
# The service — Task -> Broker -> DecisionRecord -> Approval -> Execution
# =========================================================================


def test_a_free_local_provider_runs_with_no_question_asked():
    """Deliverable 6, and the common case: nothing costs anything, nothing
    leaves the machine, so nobody is interrupted."""
    harness = Harness("alpha_runtime")

    outcome = harness.decide()

    assert outcome.ok is True
    assert outcome.selection.provider_id == "alpha-local"
    assert outcome.selection.approval_state == NOT_REQUIRED
    assert harness.mission_control.approvals.open() == []


def test_the_cheapest_provider_clearing_the_floor_wins():
    """MB031 Deliverable 8, still true through the wiring: the desktop
    subscription and the local runtime both cost nothing, so quality
    breaks the tie."""
    harness = Harness(*ALL_INSTALLED)

    assert harness.decide().selection.provider_id == "gamma-desktop"


def test_a_refusal_comes_back_as_data_rather_than_an_exception():
    """Deliverable 4. `decide()` answers; it does not throw."""
    harness = Harness(scanned=False)

    outcome = harness.decide()

    assert isinstance(outcome, SelectionOutcome)
    assert outcome.ok is False
    assert outcome.refusal.kind == NO_PROVIDER


def test_a_refusal_lists_every_provider_and_why_each_one_failed():
    harness = Harness(scanned=False)

    rejected = dict(harness.decide().refusal.rejected)

    assert len(rejected) == len(ESTATE)
    assert rejected["alpha-local"] == UNAVAILABLE


def test_select_raises_what_decide_returns():
    harness = Harness(scanned=False)

    with pytest.raises(NoProviderAvailable) as raised:
        harness.select()

    assert raised.value.refusal.kind == NO_PROVIDER


@pytest.mark.parametrize(
    ("kind", "expected"),
    [
        (APPROVAL_PENDING, ProviderApprovalPending),
        (APPROVAL_DENIED, ProviderApprovalDenied),
        (NO_PROVIDER, NoProviderAvailable),
    ],
)
def test_each_refusal_kind_raises_its_own_exception(kind, expected):
    """A caller catching "waiting on the founder" is asking a different
    question from one catching "nothing is installed"."""
    from master_agent.ai_infrastructure.service import _as_exception

    assert isinstance(_as_exception(BrokerRefusal(kind=kind, reason="x")), expected)


def test_pending_is_not_a_denial():
    """MB028.1's distinction, preserved: an unanswered question is not a
    refusal, and the class hierarchy must not let a caller conflate them."""
    assert not issubclass(ProviderApprovalPending, ProviderApprovalDenied)
    assert not issubclass(ProviderApprovalDenied, ProviderApprovalPending)


def test_a_pending_refusal_knows_it_is_still_live():
    harness = Harness(enabled=BOTH_CLOUDS)

    assert harness.decide().refusal.waiting is True


def test_a_no_provider_refusal_is_not_waiting_on_anyone():
    harness = Harness(scanned=False)

    assert harness.decide().refusal.waiting is False


def test_strong_reasoning_becomes_a_quality_floor_not_a_product():
    """The branch this replaces was `return self._provider("chatgpt")`."""
    harness = Harness(*ALL_INSTALLED, enabled=BOTH_CLOUDS, strong_floor=0.90)

    outcome = harness.decide(requires_strong_reasoning=True)

    assert outcome.refusal.kind == APPROVAL_PENDING  # epsilon-cloud, paid
    assert harness.ledger.last().quality_floor == 0.90


def test_without_strong_reasoning_the_policy_floor_applies():
    harness = Harness(*ALL_INSTALLED, strong_floor=0.90)

    harness.decide()

    assert harness.ledger.last().quality_floor == 0.6


def test_the_strictest_floor_wins_when_two_are_asked_for():
    """Taking the later one would let the order of two independent
    statements change the answer."""
    harness = Harness(*ALL_INSTALLED, strong_floor=0.90)

    harness.decide(requires_strong_reasoning=True, min_quality=0.5)

    assert harness.ledger.last().quality_floor == 0.90


def test_an_explicit_floor_above_the_strong_one_is_honoured():
    harness = Harness(*ALL_INSTALLED, strong_floor=0.70)

    harness.decide(min_quality=0.95)

    assert harness.ledger.last().quality_floor == 0.95


def test_a_service_with_no_strong_floor_configured_falls_back_to_the_policy():
    harness = Harness(*ALL_INSTALLED, strong_floor=None)

    harness.decide(requires_strong_reasoning=True)

    assert harness.ledger.last().quality_floor == 0.6


def test_a_preferred_provider_still_goes_through_the_broker():
    """An override is a constraint, not a bypass: it produces a real
    decision with a real record."""
    harness = Harness(*ALL_INSTALLED)

    outcome = harness.decide(preferred_provider="alpha-local")

    assert outcome.selection.provider_id == "alpha-local"
    assert harness.ledger.last().record is not None


def test_a_preferred_provider_excludes_the_others_on_the_record():
    """So "why not the one you would normally pick?" is answerable from
    the record rather than from someone's memory of the call."""
    harness = Harness(*ALL_INSTALLED)

    harness.decide(preferred_provider="alpha-local")
    rejected = rejections(harness.ledger.get(1).record.decision)

    assert rejected["gamma-desktop"] == EXCLUDED


def test_a_preferred_provider_that_is_unavailable_is_refused_not_used():
    harness = Harness("alpha_runtime")

    outcome = harness.decide(preferred_provider="epsilon-cloud")

    assert outcome.ok is False
    assert outcome.refusal.kind == NO_PROVIDER


def test_a_preferred_provider_below_the_floor_is_refused():
    harness = Harness(*ALL_INSTALLED)

    outcome = harness.decide(preferred_provider="beta-local-weak")

    assert outcome.ok is False
    assert dict(outcome.refusal.rejected)["beta-local-weak"] == BELOW_FLOOR


def test_an_offline_task_never_reaches_the_network():
    harness = Harness(*ALL_INSTALLED, enabled=BOTH_CLOUDS)

    outcome = harness.decide(offline=True)
    rejected = rejections(harness.ledger.get(1).record.decision)

    assert outcome.selection.provider_id == "alpha-local"
    assert rejected["gamma-desktop"] == NEEDS_NETWORK


def test_sensitive_work_never_leaves_the_machine():
    harness = Harness(*ALL_INSTALLED, enabled=BOTH_CLOUDS)

    outcome = harness.decide(sensitive=True)
    rejected = rejections(harness.ledger.get(1).record.decision)

    assert outcome.selection.provider_id == "alpha-local"
    assert rejected["gamma-desktop"] == NOT_PRIVATE
    assert rejected["epsilon-cloud"] == NOT_PRIVATE


def test_sensitive_work_under_a_permissive_policy_asks_the_founder():
    """The check exists for the policy that allows it. Every shipped
    policy filters third parties out before selection — but a policy is
    data, and the gate must not depend on today's data being safe."""
    from dataclasses import replace as dc_replace

    permissive = dc_replace(PREFER_LOCAL, require_private_for_sensitive=False)
    harness = Harness("gamma_app", policy=permissive)

    outcome = harness.decide(sensitive=True)

    assert outcome.refusal.kind == APPROVAL_PENDING
    approval = harness.mission_control.approvals.open()[0]
    assert approval.local_capability == SENSITIVE_CAPABILITY


@pytest.mark.parametrize(
    ("kwargs", "expected_field", "expected"),
    [
        ({"max_cost": 0.001}, "max_cost", 0.001),
        ({"max_latency_ms": 2000.0}, "max_latency_ms", 2000.0),
        ({"required_context_tokens": 64_000}, "required_context_tokens", 64_000),
        ({"capability": "coding"}, "capability", "coding"),
        ({"task_id": "abc"}, "task_id", "abc"),
        ({"requester": "planner"}, "requester", "planner"),
        ({"offline": True}, "offline", True),
    ],
)
def test_a_request_field_reaches_the_task_profile(kwargs, expected_field, expected):
    harness = Harness(*ALL_INSTALLED)

    task = harness.service.task_profile(SelectionRequest(**kwargs))

    assert getattr(task, expected_field) == expected


def test_a_request_with_no_capability_asks_for_reasoning():
    harness = Harness(*ALL_INSTALLED)

    assert harness.service.task_profile(SelectionRequest()).capability == DEFAULT_CAPABILITY


def test_a_request_with_no_task_id_is_given_one():
    """A decision with no task is a decision nobody can find again."""
    harness = Harness(*ALL_INSTALLED)

    assert harness.service.task_profile(SelectionRequest()).task_id == "generated-task"


def test_a_request_with_no_requester_is_attributed_to_the_router():
    harness = Harness(*ALL_INSTALLED)

    assert harness.service.task_profile(SelectionRequest()).requester == "model_router"


def test_excluded_providers_from_the_request_are_honoured():
    harness = Harness(*ALL_INSTALLED)

    outcome = harness.decide(exclude_providers=frozenset({"gamma-desktop"}))

    assert outcome.selection.provider_id == "alpha-local"


def test_a_cost_ceiling_rules_out_what_is_too_expensive():
    harness = Harness(enabled=BOTH_CLOUDS)

    outcome = harness.decide(max_cost=0.001)

    assert outcome.ok is False


def test_a_context_requirement_rules_out_a_small_window():
    harness = Harness(*ALL_INSTALLED)

    outcome = harness.decide(required_context_tokens=100_000)

    assert outcome.selection.provider_id == "gamma-desktop"


def test_a_capability_nothing_offers_is_refused():
    harness = Harness(*ALL_INSTALLED, enabled=BOTH_CLOUDS)

    outcome = harness.decide(capability="vision.ocr")

    assert outcome.ok is False
    assert outcome.refusal.capability == "vision.ocr"


def test_the_policy_in_force_is_reported():
    assert Harness().service.policy_version == "balanced/1"
    assert Harness(policy=LOWEST_COST).service.policy_version == "lowest_cost/1"


@pytest.mark.parametrize(
    ("policy", "expected"),
    [
        (LOWEST_COST, "gamma-desktop"),
        (BEST_QUALITY, "epsilon-cloud"),
        (PREFER_LOCAL, "alpha-local"),
        (PRIVACY_FIRST, "alpha-local"),
    ],
)
def test_the_founder_policy_changes_the_answer(policy, expected):
    """Eight policies, one engine. Which one is in force is a founder
    decision and it is on every record."""
    harness = Harness(*ALL_INSTALLED, enabled=BOTH_CLOUDS, policy=policy)

    outcome = harness.decide()
    chosen = outcome.selection.provider_id if outcome.ok else outcome.refusal.provider_id

    assert chosen == expected


def test_the_same_request_twice_produces_the_same_answer():
    """No caching, and no need for it: the engine is deterministic."""
    first = Harness(*ALL_INSTALLED).decide()
    second = Harness(*ALL_INSTALLED).decide()

    assert first.selection.provider_id == second.selection.provider_id
    assert (
        first.selection.decision.inputs_digest == second.selection.decision.inputs_digest
    )


def test_two_decisions_are_two_records_even_when_identical():
    harness = Harness("alpha_runtime")

    harness.decide(task_id="same")
    harness.decide(task_id="same")

    assert len(harness.ledger) == 2


def test_the_service_records_even_when_the_sink_was_not_wired():
    """Deliverable 7 says *every* AI task has a stored record. A service
    that quietly skipped one when its sink was mis-wired would break
    replay in the least visible way possible."""
    from master_agent.broker.broker import CapabilityBroker

    harness = Harness("alpha_runtime")
    unwired = AiCapabilityService(
        broker=CapabilityBroker(policy=harness.broker.policy),  # no sink
        providers=harness.providers,
        ledger=harness.ledger,
        approvals=harness.gate,
    )

    unwired.decide(SelectionRequest(task_id="t1"))

    assert len(harness.ledger) == 1
    assert harness.ledger.last().record is not None


def test_a_selection_carries_the_brokers_own_sentence():
    """Never a paraphrase: two explanations of one event eventually
    disagree."""
    harness = Harness("alpha_runtime")

    selection = harness.decide().selection

    assert selection.why == selection.decision.reason
    assert "clears the floor" in selection.why


@pytest.mark.parametrize(
    ("field", "expected"),
    [
        ("provider_id", "alpha-local"),
        ("cost_tier", tiers.FREE),
        ("quality_tier", tiers.GOOD),
        ("approval_state", NOT_REQUIRED),
        ("task_id", "t1"),
    ],
)
def test_a_selection_exposes_what_a_caller_needs(field, expected):
    harness = Harness("alpha_runtime")

    assert getattr(harness.decide().selection, field) == expected


def test_a_selection_serialises_for_a_front_end():
    harness = Harness("alpha_runtime")

    payload = harness.decide().selection.as_dict()

    assert payload["provider_id"] == "alpha-local"
    assert payload["policy_version"] == "balanced/1"
    assert payload["approval_state"] == NOT_REQUIRED


def test_an_outcome_serialises_either_way():
    good = Harness("alpha_runtime").decide().as_dict()
    bad = Harness(scanned=False).decide().as_dict()

    assert good["ok"] is True
    assert bad["ok"] is False
    assert bad["refusal"]["kind"] == NO_PROVIDER


def test_a_refusal_serialises_with_every_rejection():
    harness = Harness(scanned=False)

    payload = harness.decide().refusal.as_dict()

    assert len(payload["rejected"]) == len(ESTATE)
    assert {"provider_id", "reason"} == set(payload["rejected"][0])


def test_an_outcome_is_never_both_and_never_neither():
    good = Harness("alpha_runtime").decide()
    bad = Harness(scanned=False).decide()

    assert (good.selection is None) != (good.refusal is None)
    assert (bad.selection is None) != (bad.refusal is None)


def test_refusal_from_decision_reuses_the_brokers_reason():
    harness = Harness(scanned=False)
    harness.decide()
    decision = harness.ledger.get(1).record.decision

    assert refusal_from_decision(decision).reason == decision.reason


def test_the_service_exposes_the_estate_it_decided_over():
    harness = Harness("alpha_runtime")

    assert len(harness.service.profiles()) == len(ESTATE)


# ---- the report the Dashboard reads -------------------------------------


def test_the_report_states_the_policy_and_the_estate():
    harness = Harness(*ALL_INSTALLED, enabled=BOTH_CLOUDS)

    report = harness.service.report()

    assert report.policy_version == "balanced/1"
    assert report.policy_name == "balanced"
    assert report.providers_available == 5
    assert report.providers_total == 5
    assert report.scanned is True


def test_the_report_counts_decisions_and_open_questions():
    harness = Harness("alpha_runtime", enabled=BOTH_CLOUDS)
    harness.decide(task_id="free")
    harness.decide(task_id="paid", min_quality=0.9)

    report = harness.service.report()

    assert report.total_decisions == 2
    assert report.awaiting_approval == 1


def test_the_report_shows_the_most_recent_decisions_first():
    harness = Harness("alpha_runtime")
    for index in range(5):
        harness.decide(task_id=f"t{index}")

    assert [e.task_id for e in harness.service.report(limit=2).decisions] == ["t4", "t3"]


def test_the_report_surfaces_recording_problems_rather_than_hiding_them():
    class Broken:
        def read(self):
            return []

        def write(self, _rows):
            raise OSError("disk full")

    harness = Harness("alpha_runtime", store=Broken())
    harness.decide()

    assert any("disk full" in problem for problem in harness.service.report().recording_failures)


def test_an_unscanned_machine_is_reported_as_unscanned():
    assert Harness(scanned=False).service.report().scanned is False


# =========================================================================
# The Model Router — Deliverables 1, 10, 11
# =========================================================================


def router(selector=None, providers=()) -> ModelRouter:
    registry = PluginRegistry()
    for provider in providers:
        registry.register(provider)
    return ModelRouter(registry, selector=selector)


def test_a_router_with_no_broker_knows_it():
    assert router().has_broker is False
    assert router(selector=Harness().service).has_broker is True


@pytest.mark.parametrize("call", ["select", "select_provider"])
def test_a_router_with_no_broker_refuses_rather_than_guessing(call):
    """Deliverable 10, and the whole point of MB032: a fallback *is* a
    provider decision, and making one when the decision-maker is missing
    is the hardcoding this brief deleted."""
    with pytest.raises(BrokerUnavailable) as raised:
        getattr(router(), call)(RoutingContext())

    assert str(raised.value) == NO_SELECTOR


def test_generating_without_a_broker_refuses_before_any_provider_is_touched():
    provider = RecordingProvider("alpha-local")

    with pytest.raises(BrokerUnavailable):
        router(providers=[provider]).generate("hello", RoutingContext())

    assert provider.calls == []


def test_the_router_returns_the_provider_the_broker_chose():
    harness = Harness("alpha_runtime")
    provider = RecordingProvider("alpha-local")

    chosen = router(harness.service, [provider]).select_provider(RoutingContext())

    assert chosen is provider


def test_the_router_asks_the_broker_before_resolving_anything():
    harness = Harness("alpha_runtime")

    selection = router(harness.service).select(RoutingContext(task_id="t9"))

    assert selection.provider_id == "alpha-local"
    assert harness.ledger.for_task("t9") is not None


def test_a_chosen_provider_with_no_plugin_is_a_wiring_error_not_a_new_choice():
    """Silently picking a different provider would make the record a
    lie."""
    harness = Harness("alpha_runtime")

    with pytest.raises(ProviderNotWired) as raised:
        router(harness.service).select_provider(RoutingContext())

    assert "alpha-local" in str(raised.value)
    assert raised.value.provider_id == "alpha-local"


def test_a_plugin_that_is_not_a_model_provider_is_a_wiring_error():
    class NotAModel(Plugin):
        @property
        def manifest(self):
            return PluginManifest(name="alpha-local", version="1", capabilities=[])

        def invoke(self, capability, payload):
            raise AssertionError("never called")

    harness = Harness("alpha_runtime")

    with pytest.raises(ProviderNotWired) as raised:
        router(harness.service, [NotAModel()]).select_provider(RoutingContext())

    assert "not a ModelProvider" in str(raised.value)


def test_generate_forwards_the_prompt_and_the_context():
    harness = Harness("alpha_runtime")
    provider = RecordingProvider("alpha-local", reply="done")

    answer = router(harness.service, [provider]).generate(
        "summarise this", RoutingContext(), {"file": "notes.md"}
    )

    assert answer == "done"
    assert provider.calls == [("summarise this", {"file": "notes.md"})]


@pytest.mark.parametrize(
    "scenario",
    [
        ("no_provider", NoProviderAvailable),
        ("pending", ProviderApprovalPending),
    ],
)
def test_a_broker_refusal_reaches_the_caller_untouched(scenario):
    """The caller must see *why*. The router has nothing to add to a
    reason the Broker already wrote."""
    kind, expected = scenario
    harness = Harness(scanned=False) if kind == "no_provider" else Harness(enabled=BOTH_CLOUDS)

    with pytest.raises(expected):
        router(harness.service).select_provider(RoutingContext())


def test_a_rejected_provider_reaches_the_caller_as_a_denial():
    harness = Harness(enabled=BOTH_CLOUDS)
    harness.decide(task_id="t-denied")
    harness.reject_everything()

    with pytest.raises(ProviderApprovalDenied):
        router(harness.service).select_provider(RoutingContext(task_id="t-denied"))


@pytest.mark.parametrize(
    ("context_kwargs", "field", "expected"),
    [
        ({}, "capability", REASONING),
        ({"capability": "coding"}, "capability", "coding"),
        ({"is_online": True}, "offline", False),
        ({"is_online": False}, "offline", True),
        ({"is_sensitive": True}, "sensitive", True),
        ({"is_sensitive": False}, "sensitive", False),
        ({"requires_strong_reasoning": True}, "requires_strong_reasoning", True),
        ({"preferred_provider": "x"}, "preferred_provider", "x"),
        ({"max_cost": 0.5}, "max_cost", 0.5),
        ({"max_latency_ms": 100.0}, "max_latency_ms", 100.0),
        ({"required_context_tokens": 9}, "required_context_tokens", 9),
        ({"task_id": "t"}, "task_id", "t"),
        ({"objective_id": "o"}, "objective_id", "o"),
        ({"requester": "planner"}, "requester", "planner"),
    ],
)
def test_a_routing_context_becomes_a_selection_request(context_kwargs, field, expected):
    request = SelectionRequest.from_context(RoutingContext(**context_kwargs))

    assert getattr(request, field) == expected


def test_online_becomes_offline_because_the_broker_asks_about_the_constraint():
    assert SelectionRequest.from_context(RoutingContext(is_online=False)).offline is True


def test_a_selection_request_is_frozen():
    from dataclasses import FrozenInstanceError

    with pytest.raises(FrozenInstanceError):
        SelectionRequest().capability = "coding"  # type: ignore[misc]


def test_the_selector_port_is_satisfied_by_the_service():
    assert isinstance(Harness().service, ProviderSelector)


def test_the_selector_port_is_one_method_wide():
    """The Brain must not be able to reach a policy, a profile list, or a
    ledger through it."""
    members = {name for name in dir(ProviderSelector) if not name.startswith("_")}

    assert members == {"select"}


# =========================================================================
# The small surfaces — accessors, and the defensive branches under them
# =========================================================================


def test_the_service_exposes_the_broker_it_consults():
    harness = Harness("alpha_runtime")

    assert harness.service.broker is harness.broker
    assert harness.service.ledger is harness.ledger
    assert harness.service.providers is harness.providers


def test_a_selection_carries_the_record_behind_it():
    """So a caller holding a selection can replay it without going back to
    the ledger."""
    harness = Harness("alpha_runtime")

    selection = harness.decide().selection

    assert selection.record is harness.ledger.get(1).record


def test_the_source_reports_the_specs_it_was_given():
    assert source("alpha_runtime").specs == ESTATE


def test_a_refusal_exception_reports_its_kind():
    from master_agent.ai_infrastructure.refusal import BrokerRefused

    raised = BrokerRefused(BrokerRefusal(kind=NO_PROVIDER, reason="nothing"))

    assert raised.kind == NO_PROVIDER
    assert str(raised) == "nothing"


def test_a_pending_exception_names_the_approval_directly():
    """A caller catching this wants one thing: the number the founder has
    to answer."""
    pending = ProviderApprovalPending(
        BrokerRefusal(kind=APPROVAL_PENDING, reason="waiting", approval_id="ab12")
    )

    assert pending.approval_id == "ab12"


def test_a_pending_refusal_points_at_the_ledger_entry_it_belongs_to():
    """So the panel showing "waiting on you" and the record explaining why
    are the same decision, not two that look alike."""
    harness = Harness(enabled=BOTH_CLOUDS)

    outcome = harness.decide()

    assert outcome.refusal.entry_id == harness.ledger.last().entry_id


def test_an_unreadable_objective_is_not_a_reason_to_skip_the_question():
    """The founder still has to be asked. A dispatcher that cannot answer
    "which mission is this?" costs a line of context, not the approval."""

    class BrokenDispatcher:
        def objectives(self):
            raise RuntimeError("dispatcher unavailable")

    harness = Harness(enabled=BOTH_CLOUDS)
    harness.mission_control.dispatcher = BrokenDispatcher()

    outcome = harness.decide(objective_id="anything")

    assert outcome.refusal.kind == APPROVAL_PENDING
    assert harness.mission_control.approvals.open()[0].objective is None


def test_an_in_memory_store_reads_back_what_it_was_given():
    store = InMemoryDecisionStore()
    store.write([{"entry_id": 1}])

    assert store.read() == [{"entry_id": 1}]
    assert store.read() is not store.rows


def test_a_write_that_fails_leaves_no_temporary_file_behind(tmp_path):
    """Atomic means atomic: the previous good ledger survives, and the
    directory is not littered with half-written attempts."""
    blocked = tmp_path / "decisions.json"
    blocked.mkdir()  # a directory where the file should go
    store = JsonFileDecisionStore(blocked)

    with pytest.raises(OSError):
        store.write([{"entry_id": 1}])

    assert list(tmp_path.glob("*.tmp")) == []


# =========================================================================
# Architecture purity — the forbidden list, asserted
# =========================================================================

FORBIDDEN_MODULES = (
    "subprocess",
    "socket",
    "http",
    "httpx",
    "requests",
    "urllib",
    "openai",
    "anthropic",
)

VENDORS = ("openrouter", "ollama", "claude", "gemini", "gpt-", "llama", "mistral", "qwen")


def _imported(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


@pytest.mark.parametrize("module", FORBIDDEN_MODULES)
def test_the_wiring_layer_cannot_reach_a_provider_either(module):
    """The Broker decides and the Executive executes. This layer does
    neither, so it has no business holding a network client."""
    for path in MODULES:
        for name in _imported(path):
            assert not name.startswith(module), f"{path.name} imports {name}"


@pytest.mark.parametrize(
    "forbidden", ["invoke", "execute", "launch", "download", "install"]
)
def test_the_wiring_layer_performs_nothing_itself(forbidden):
    """MB033 refined this rule rather than relaxing it.

    This layer now *invokes* a provider — that is what MB033 assigns it —
    but through an object it was handed, never machinery of its own. So
    the surface it must not grow is unchanged: nothing here launches,
    downloads, installs, or defines its own execute. Combined with the
    import test above (no transport of any kind), "it can ask a provider
    to run something" and "it can run something" stay different facts.

    Checked by AST rather than by substring: the first version searched
    for the text `def execute` and matched `def executed`, a read-only
    property. That is the same false positive MB032 hit with `find_open`.
    """
    for path in MODULES:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                assert node.name != forbidden, f"{path.name} defines {node.name}()"


@pytest.mark.parametrize("vendor", VENDORS)
def test_only_the_catalogue_names_a_provider(vendor):
    """Provider identity is allowed in exactly one file — the same
    containment `desktop/catalog.py` has for install paths. Everywhere
    else, a provider is an id that came out of a DecisionRecord."""
    for path in MODULES:
        if path.name == "catalog.py":
            continue
        text = path.read_text(encoding="utf-8").lower()
        assert vendor not in text, f"'{vendor}' appears in {path.name}"


@pytest.mark.parametrize("vendor", VENDORS)
def test_the_model_router_names_no_provider_at_all(vendor):
    """The whole point of Deliverable 11. Before MB032 this file contained
    two of these."""
    assert vendor not in ROUTER.read_text(encoding="utf-8").lower()


def test_the_model_router_holds_no_default_provider():
    """Deliverable 11. Checked against the *code* rather than the file
    text, because the module docstring quotes the deleted branches on
    purpose -- a reader six months from now needs to see what this used to
    do, and a grep would forbid saying so."""
    tree = ast.parse(ROUTER.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.arg):
            assert node.arg != "default_provider"
        if isinstance(node, ast.Attribute):
            assert node.attr != "_default_provider"
        if isinstance(node, ast.Name):
            assert node.id != "default_provider"


def test_the_model_router_depends_on_nothing_but_the_plugin_contract():
    """A router that dragged Mission Control into every importer would
    have moved the coupling rather than removed it."""
    imported = _imported(ROUTER)
    internal = {name for name in imported if name.startswith("master_agent")}

    assert internal <= {"master_agent.plugins.base", "master_agent.plugins.registry"}


def test_the_wiring_layer_holds_no_ranking():
    """ADR-0018's Consequences name a ranking function growing outside the
    Broker as *the* failure mode that would invalidate the design. Checked
    structurally: nothing here sorts a provider collection."""
    for path in MODULES:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = getattr(node.func, "id", "") or getattr(node.func, "attr", "")
                if name == "sorted":
                    keywords = {k.arg for k in node.keywords}
                    assert "key" not in keywords or path.name in ("service.py",), (
                        f"{path.name} sorts with a key -- is it ranking providers?"
                    )


def test_the_only_sort_in_the_wiring_layer_is_by_provider_id():
    """The one `sorted(key=...)` allowed above, pinned to what it actually
    is: canonical ordering for the record, which the Broker does too, and
    which is the opposite of a ranking."""
    text = (PACKAGE_DIR / "service.py").read_text(encoding="utf-8")

    assert "sorted(profiles, key=lambda p: p.provider_id)" in text
    assert text.count("sorted(") == 1


def test_the_broker_package_still_depends_on_nothing():
    """MB031's invariant, re-asserted from the other side: MB032 wired the
    Broker up without reaching back into it."""
    broker_dir = REPO_ROOT / "src" / "master_agent" / "broker"
    for path in broker_dir.rglob("*.py"):
        for name in _imported(path):
            if name.startswith("master_agent"):
                assert name.startswith("master_agent.broker"), f"{path.name}: {name}"


def test_the_runtime_still_knows_nothing_about_providers():
    """Rule 6: the Runtime must remain provider-agnostic. It never learned
    about the Broker, because it never needed to — selection happens
    before dispatch, not inside it (ADR-0017 Decision 1)."""
    runtime_dir = REPO_ROOT / "src" / "master_agent" / "runtime"
    for path in runtime_dir.glob("*.py"):
        for name in _imported(path):
            assert not name.startswith("master_agent.ai_infrastructure")
            assert not name.startswith("master_agent.broker")
            assert not name.startswith("master_agent.plugins.model_router")


def test_mission_control_still_knows_nothing_about_providers():
    mission_dir = REPO_ROOT / "src" / "master_agent" / "mission_control"
    for path in mission_dir.glob("*.py"):
        for name in _imported(path):
            assert not name.startswith("master_agent.ai_infrastructure")
            assert not name.startswith("master_agent.broker")


def test_the_dashboard_reads_a_report_rather_than_importing_the_broker():
    """ADR-0016 Decision 5, applied to decisions: handed in, never
    discovered."""
    dashboard_dir = REPO_ROOT / "src" / "master_agent" / "dashboard"
    for path in dashboard_dir.glob("*.py"):
        for name in _imported(path):
            assert not name.startswith("master_agent.ai_infrastructure")
            assert not name.startswith("master_agent.broker")


def test_the_desktop_executive_still_decides_nothing():
    """MB030's Rules 2 and 11 survive MB032: the Desktop Executive reports
    what is installed and this layer reads it. The dependency points one
    way, and the wrong direction would make the scanner a chooser."""
    desktop_dir = REPO_ROOT / "src" / "master_agent" / "desktop"
    for path in desktop_dir.rglob("*.py"):
        for name in _imported(path):
            assert not name.startswith("master_agent.ai_infrastructure")
            assert not name.startswith("master_agent.broker")


def test_the_wiring_layer_reads_the_machine_through_the_desktop_executive_only():
    """No second door to the Environment (Constitution Rule 4). This
    package opens no file of its own -- except the ledger, whose whole job
    is one JSON document.

    Checked by AST rather than by grep: the first version of this test
    searched for the string `open(` and failed on
    `approvals.find_open(...)`, which is a queue lookup and not a file at
    all.
    """
    for path in MODULES:
        if path.name == "ledger.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id != "open", f"{path.name} opens a file"


def test_every_public_module_documents_which_deliverable_it_serves():
    """A file whose reason for existing is not written down is a file
    somebody deletes or duplicates six months later."""
    for path in MODULES:
        if path.name == "__init__.py":
            continue
        head = " ".join(path.read_text(encoding="utf-8")[:600].split())
        assert '"""' in head, f"{path.name} has no docstring"
        assert any(
            marker in head
            for marker in (
                "Mission Brief 032",
                "MB032",
                "Mission Brief 033",
                "MB033",
                # MB038 added `workload.py` and `budgets.py` to this
                # package. The convention is "say which brief you serve";
                # a newer brief is a valid answer, not an exception.
                "Mission Brief 038",
                "MB038",
            )
        ), path.name
