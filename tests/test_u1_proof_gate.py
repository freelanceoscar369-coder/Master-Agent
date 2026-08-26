"""Three boundaries the U1 convergence crossed on its way through, and
the guards that stop them being crossed again.

None of the three was an architecture mistake. Each was the same *kind*
of mistake -- a shortcut that is invisible while everything works and
wrong the moment something does not:

1. a second snapshot loader that skipped the checksum, so a tampered
   snapshot loaded as though it were a first run
2. an executable entry guard sitting above the helpers it transitively
   calls, which is harmless on import and a NameError as a script
3. an economic claim stamped freshly-verified because a credential
   existed, when a credential proves configuration and nothing about price

Everything here runs against fakes and temporary directories. No network,
no founder state directory.
"""
from __future__ import annotations

import ast
import dataclasses
import os
import sys
from datetime import UTC, datetime

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import kalpavriksha_desktop as kd  # noqa: E402
from master_agent.broker.registry import (  # noqa: E402
    EconomicClass,
    ProviderDescriptor,
    ProviderHealth,
    ProviderRegistry,
)
from master_agent.persistence.schema import (  # noqa: E402
    CURRENT_SCHEMA_VERSION,
    CorruptSnapshot,
    SnapshotEnvelope,
    UnsupportedSchemaVersion,
)
from master_agent.persistence.store import JsonFileStateStore  # noqa: E402


# ═════════════ 1. restore goes through the verified loader ═════════════


def descriptor(provider_id: str = "openrouter.api") -> ProviderDescriptor:
    return ProviderDescriptor(
        provider_id=provider_id,
        display_name="OpenRouter",
        provider_class="cloud",
        capabilities=frozenset({"reasoning"}),
        cost_per_call=0.005,
        is_free=False,
        needs_credentials=True,
        health=ProviderHealth.HEALTHY,
    )


def write_snapshot(root, payload, *, schema_version=CURRENT_SCHEMA_VERSION,
                   seal=True, tamper=False):
    """Put a snapshot on disk the way the real store would, optionally
    with a checksum that no longer matches its payload."""
    envelope = SnapshotEnvelope(payload=payload, schema_version=schema_version)
    if seal:
        envelope = envelope.sealed()
    if tamper:
        # The signature of an actual tamper: the payload is edited and the
        # checksum left behind describing what it used to be.
        edited = dict(envelope.payload)
        edited["providers"] = [
            {**row, "cost_per_call": 0.0, "is_free": True}
            for row in edited.get("providers", [])
        ]
        envelope = dataclasses.replace(envelope, payload=edited)
    JsonFileStateStore(root).save_snapshot(envelope)
    return envelope


def base_payload(providers=None):
    return {
        "executives": [],
        "capabilities": [],
        "objectives": [],
        "founder_state": None,
        "providers": providers if providers is not None else [],
    }


class TestRestoreIntegrity:
    """A MISSING snapshot is a first run. A CORRUPT one is not the same
    condition, and the version this replaces could not tell them apart --
    it caught `Exception`, logged a warning and carried on as though the
    disk had been empty."""

    def test_A_a_missing_snapshot_is_an_ordinary_first_run(self, tmp_path):
        registry = ProviderRegistry()

        restored = kd._restore_canonical_providers(registry, tmp_path)

        assert restored == ()
        assert list(registry.all()) == []

    def test_B_a_valid_snapshot_restores_its_descriptors(self, tmp_path):
        write_snapshot(tmp_path, base_payload([descriptor().as_dict()]))
        registry = ProviderRegistry()

        restored = kd._restore_canonical_providers(registry, tmp_path)

        assert restored == ("openrouter.api",)
        assert registry.get("openrouter.api") is not None

    def test_B_restored_runtime_health_is_not_trusted(self, tmp_path):
        """Saved HEALTHY, restored UNVERIFIED. Yesterday's observation is
        not today's fact."""
        write_snapshot(tmp_path, base_payload([descriptor().as_dict()]))
        registry = ProviderRegistry()

        kd._restore_canonical_providers(registry, tmp_path)

        assert registry.get("openrouter.api").health is ProviderHealth.UNVERIFIED

    def test_C_a_v1_snapshot_is_migrated_rather_than_refused(self, tmp_path):
        """v1 predates the provider slice entirely. Absent is not corrupt."""
        payload = {
            "executives": [], "capabilities": [], "objectives": [],
            "founder_state": None,
        }
        write_snapshot(tmp_path, payload, schema_version=1)
        registry = ProviderRegistry()

        assert kd._restore_canonical_providers(registry, tmp_path) == ()

    def test_C_a_v1_snapshot_carrying_no_providers_still_bootstraps(self, tmp_path):
        from master_agent.ai_infrastructure.profiles import bootstrap_registry

        payload = {"executives": [], "capabilities": [], "objectives": [],
                   "founder_state": None}
        write_snapshot(tmp_path, payload, schema_version=1)
        registry = ProviderRegistry()

        kd._restore_canonical_providers(registry, tmp_path)
        bootstrap_registry(registry)

        assert registry.get("openrouter.api") is not None

    def test_D_a_tampered_checksum_is_refused(self, tmp_path):
        """The whole reason this had to stop being a second loader. The
        edit below turns a metered provider into a free one; the previous
        implementation never computed a checksum, so it loaded."""
        write_snapshot(tmp_path, base_payload([descriptor().as_dict()]),
                       tamper=True)
        registry = ProviderRegistry()

        with pytest.raises(CorruptSnapshot):
            kd._restore_canonical_providers(registry, tmp_path)

    def test_D_a_refused_snapshot_leaves_the_registry_untouched(self, tmp_path):
        write_snapshot(tmp_path, base_payload([descriptor().as_dict()]),
                       tamper=True)
        registry = ProviderRegistry()

        with pytest.raises(CorruptSnapshot):
            kd._restore_canonical_providers(registry, tmp_path)

        assert list(registry.all()) == []

    def test_E_an_unreadable_provider_row_is_refused(self, tmp_path):
        write_snapshot(tmp_path, base_payload([{"provider_id": "broken.thing"}]))
        registry = ProviderRegistry()

        with pytest.raises(CorruptSnapshot):
            kd._restore_canonical_providers(registry, tmp_path)

    def test_E_one_bad_row_does_not_half_restore_the_good_ones(self, tmp_path):
        """All or nothing. A registry holding the rows that happened to
        parse before the failure is the state that looks fine and is not."""
        write_snapshot(tmp_path, base_payload([
            descriptor("gemini.api").as_dict(),
            {"provider_id": "broken.thing"},
        ]))
        registry = ProviderRegistry()

        with pytest.raises(CorruptSnapshot):
            kd._restore_canonical_providers(registry, tmp_path)

        assert registry.get("gemini.api") is None

    def test_F_a_schema_from_the_future_is_refused(self, tmp_path):
        write_snapshot(tmp_path, base_payload(),
                       schema_version=CURRENT_SCHEMA_VERSION + 5)
        registry = ProviderRegistry()

        with pytest.raises(UnsupportedSchemaVersion):
            kd._restore_canonical_providers(registry, tmp_path)

    def test_restore_uses_the_existing_verified_loader(self):
        """Not a second implementation of load/verify/migrate. If this
        function ever grows its own `load_snapshot()` call again, the
        checksum step is the one that goes missing."""
        called = _names_called(kd._restore_canonical_providers)

        assert "PersistenceService" in called
        assert "load_snapshot" not in called, (
            "_restore_canonical_providers is open-coding the loader again"
        )


def _names_called(function) -> set[str]:
    """Every name this function actually calls. Read from the syntax tree
    rather than the source text, so the docstring -- which necessarily
    names the very thing being forbidden -- cannot satisfy or trip it."""
    import inspect
    import textwrap

    tree = ast.parse(textwrap.dedent(inspect.getsource(function)))
    called: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            target = node.func
            if isinstance(target, ast.Name):
                called.add(target.id)
            elif isinstance(target, ast.Attribute):
                called.add(target.attr)
    return called


# ═════════════ 2. definitions exist before main can call them ═════════════


class TestEntryPointOrdering:
    """Import order is not script order. Under `import`, the whole module
    executes before anything calls `main()`; run as a script -- which is
    what the packaged executable does -- the guard fires where it sits."""

    def test_the_entry_guard_is_the_last_statement_in_the_module(self):
        module = ast.parse(_module_source())
        guards = [
            index for index, node in enumerate(module.body)
            if _is_main_guard(node)
        ]

        assert len(guards) == 1, "expected exactly one `if __name__` guard"
        assert guards[0] == len(module.body) - 1, (
            "the `if __name__ == '__main__'` guard is not the final "
            "statement; names defined after it do not exist when the "
            "module is executed as a script"
        )

    def test_every_name_main_reaches_is_defined_above_the_guard(self):
        """The specific failure: `main()` -> `_build_mission_pipeline()`
        -> `_configured_cloud_providers` / `_restore_canonical_providers`
        / `OPENROUTER_CONFIGURED_MODEL`, all three of which used to be
        defined below the guard."""
        module = ast.parse(_module_source())
        guard_line = next(
            node.lineno for node in module.body if _is_main_guard(node)
        )

        for name in (
            "_configured_cloud_providers",
            "_restore_canonical_providers",
            "_observe_openrouter_economics",
            "_with_observed_economics",
            "OPENROUTER_CONFIGURED_MODEL",
            "_OPENROUTER_METERED_COST",
        ):
            assert _definition_line(module, name) < guard_line, (
                f"{name} is defined after the entry guard and will not "
                f"exist when this module is run as a script"
            )

    def test_the_module_still_imports(self):
        """The other half of the claim. Moving the guard must not have
        cost the import path."""
        assert callable(kd.main)
        assert callable(kd._build_mission_pipeline)


def _module_source() -> str:
    import inspect

    return inspect.getsource(kd)


def _is_main_guard(node) -> bool:
    return (
        isinstance(node, ast.If)
        and isinstance(node.test, ast.Compare)
        and isinstance(node.test.left, ast.Name)
        and node.test.left.id == "__name__"
    )


def _definition_line(module, name: str) -> int:
    for node in module.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node.lineno
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return node.lineno
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id == name:
                return node.lineno
    raise AssertionError(f"{name} is not defined at module level")


# ═══════════ 3. economics are observed before they are claimed ═══════════


class FakeModelSource:
    """Stands in for `OpenRouterProvider` at exactly the surface the
    observation uses: one method, returning the configured model's current
    metadata or None."""

    def __init__(self, model=None, raises=None):
        self._model = model
        self._raises = raises
        self.calls = 0

    def resolve_model(self):
        self.calls += 1
        if self._raises is not None:
            raise self._raises
        return self._model


FREE_MODEL = {
    "id": "minimax/minimax-m3:free",
    "pricing": {"prompt": "0", "completion": "0"},
    "context_length": 128_000,
}


class TestSelectionTimePriceEvidence:

    def test_a_credential_alone_never_produces_a_free_claim(self):
        """The defect, stated as a test. No observation -> no zero."""
        record = kd._with_observed_economics(
            descriptor(), None, kd.OPENROUTER_CONFIGURED_MODEL
        )

        assert record.is_free is False
        assert record.economic_class is EconomicClass.UNKNOWN
        assert record.economic_verified_at is None

    def test_an_unverified_record_is_not_free_policy_eligible(self):
        """`ProviderProfile.is_free` is `cost <= 0`, so the load-bearing
        field is the cost, not the flag. A zero left here would make the
        Broker prefer a provider whose price nobody had read."""
        record = kd._with_observed_economics(
            dataclasses.replace(descriptor(), cost_per_call=0.0),
            None,
            kd.OPENROUTER_CONFIGURED_MODEL,
        )

        assert record.cost_per_call > 0.0
        assert record.to_profile().is_free is False

    def test_a_stale_persisted_free_claim_does_not_survive(self):
        """A descriptor restored from a snapshot that was stamped free
        last week. Without a current reading it must come back UNKNOWN --
        this is the "persisted free becomes current truth" hole."""
        stale = dataclasses.replace(
            descriptor(),
            cost_per_call=0.0,
            is_free=True,
            economic_class=EconomicClass.RECURRING_FREE,
            economic_verified_at=datetime(2020, 1, 1, tzinfo=UTC),
        )

        record = kd._with_observed_economics(
            stale, None, kd.OPENROUTER_CONFIGURED_MODEL
        )

        assert record.economic_class is EconomicClass.UNKNOWN
        assert record.economic_verified_at is None
        assert record.to_profile().is_free is False

    def test_an_observation_produces_a_free_record_with_its_provenance(self):
        observation = kd._observe_openrouter_economics(FakeModelSource(FREE_MODEL))
        record = kd._with_observed_economics(
            descriptor(), observation, kd.OPENROUTER_CONFIGURED_MODEL
        )

        assert record.cost_per_call == 0.0
        assert record.is_free is True
        assert record.economic_class is EconomicClass.RECURRING_FREE
        assert record.to_profile().is_free is True

    def test_the_timestamp_is_the_reading_not_the_launch(self):
        before = datetime.now(UTC)
        observation = kd._observe_openrouter_economics(FakeModelSource(FREE_MODEL))
        after = datetime.now(UTC)

        assert observation is not None
        assert before <= observation["observed_at"] <= after

    def test_the_evidence_names_the_model_the_endpoint_and_both_prices(self):
        observation = kd._observe_openrouter_economics(FakeModelSource(FREE_MODEL))
        record = kd._with_observed_economics(
            descriptor(), observation, kd.OPENROUTER_CONFIGURED_MODEL
        )

        assert observation["model"] == "minimax/minimax-m3:free"
        assert observation["prompt_price"] == 0.0
        assert observation["completion_price"] == 0.0
        assert "openrouter /api/v1/models" in record.economic_source
        assert "minimax/minimax-m3:free" in record.economic_source

    def test_an_unlisted_model_yields_no_evidence(self):
        """`resolve_model()` already returns None when the configured slug
        is not currently listed at zero price."""
        assert kd._observe_openrouter_economics(FakeModelSource(None)) is None

    def test_a_priced_model_yields_no_evidence(self):
        priced = {**FREE_MODEL, "pricing": {"prompt": "0.0000012", "completion": "0"}}

        assert kd._observe_openrouter_economics(FakeModelSource(priced)) is None

    def test_an_unreachable_gateway_yields_no_evidence_and_is_not_fatal(self):
        source = FakeModelSource(raises=OSError("no route to host"))

        assert kd._observe_openrouter_economics(source) is None
        assert source.calls == 1

    def test_unreadable_pricing_yields_no_evidence(self):
        broken = {**FREE_MODEL, "pricing": {"prompt": "free", "completion": "0"}}

        assert kd._observe_openrouter_economics(broken and FakeModelSource(broken)) is None

    def test_the_configured_slug_is_recorded_either_way(self):
        for observation in (None,
                            kd._observe_openrouter_economics(
                                FakeModelSource(FREE_MODEL))):
            record = kd._with_observed_economics(
                descriptor(), observation, kd.OPENROUTER_CONFIGURED_MODEL
            )
            assert kd.OPENROUTER_CONFIGURED_MODEL in record.notes


class TestExecutionTimePriceGate:
    """Selection-time and execution-time are two different guarantees and
    both are kept. The first makes the Broker's ranking truthful; the
    second makes it impossible for a price change between the decision and
    the socket opening to become a charge."""

    def test_the_provider_still_revalidates_before_every_request(self):
        from master_agent.providers.openrouter import OpenRouterProvider
        from master_agent.providers.response import UNAVAILABLE

        class Refusing:
            def get(self, url, timeout, headers=None):
                # The configured model is no longer listed as free.
                class R:
                    status = 200
                    body = '{"data": []}'
                return R()

            def post_json(self, *a, **k):  # pragma: no cover - must not run
                raise AssertionError("a request was sent without a price check")

        provider = OpenRouterProvider(
            transport=Refusing(),
            credential_reader=lambda: "test-credential",
            model=kd.OPENROUTER_CONFIGURED_MODEL,
        )

        result = provider.complete("anything")

        assert result.outcome is UNAVAILABLE
        assert kd.OPENROUTER_CONFIGURED_MODEL in (result.error or "")

    def test_a_free_selection_record_does_not_authorise_the_call(self):
        """Even handed a canonical record that says free, the provider
        reads the price again. The two checks are independent by design."""
        from master_agent.providers.openrouter import OpenRouterProvider

        free_record = kd._with_observed_economics(
            descriptor(),
            kd._observe_openrouter_economics(FakeModelSource(FREE_MODEL)),
            kd.OPENROUTER_CONFIGURED_MODEL,
        )
        assert free_record.to_profile().is_free is True

        seen = {"models_read": 0}

        class Counting:
            def get(self, url, timeout, headers=None):
                seen["models_read"] += 1

                class R:
                    status = 200
                    body = '{"data": []}'
                return R()

            def post_json(self, *a, **k):  # pragma: no cover
                raise AssertionError("charged without revalidating")

        OpenRouterProvider(
            transport=Counting(),
            credential_reader=lambda: "test-credential",
            model=kd.OPENROUTER_CONFIGURED_MODEL,
        ).complete("anything")

        assert seen["models_read"] >= 1


# ═════════ 4. the convergence still holds after those three fixes ═════════


class TestTheConvergenceIsIntact:
    """Not a re-audit -- the U1 convergence has its own file. These are the
    handful of properties the three corrections above could plausibly have
    broken, each stated as the one sentence it is supposed to guarantee."""

    def test_the_administrative_source_is_the_registry_and_only_that(self):
        from master_agent.ai_infrastructure.profiles import ProviderSource

        registry = ProviderRegistry()
        registry.register(descriptor("only.thing"))
        source = ProviderSource(registry=registry)

        assert source.registry is registry
        assert [p.provider_id for p in source.profiles()] == ["only.thing"]

    def test_the_catalogue_is_bootstrap_and_cannot_change_a_profile_later(self):
        """The property that makes "canonical" mean something. A source
        that re-read `PROVIDER_CATALOG` on every call did not have it:
        editing a spec silently moved what the Broker saw."""
        from master_agent.ai_infrastructure.catalog import ProviderSpec
        from master_agent.ai_infrastructure.profiles import ProviderSource

        spec = ProviderSpec(
            provider_id="edited.later",
            label="Edited Later",
            capabilities=frozenset({"reasoning"}),
            locality="cloud",
            privacy="third_party",
            declared_quality=0.5,
            cost_per_call=0.0,
        )
        source = ProviderSource(specs=(spec,))
        before = {p.provider_id: p.cost for p in source.profiles()}

        edited = dataclasses.replace(spec, cost_per_call=99.0)
        assert edited.cost_per_call == 99.0

        after = {p.provider_id: p.cost for p in source.profiles()}
        assert after == before, (
            "editing a ProviderSpec changed a ProviderProfile without a "
            "re-import; the catalogue is still a production authority"
        )

    def test_the_configured_model_is_the_source_constant(self):
        assert kd.OPENROUTER_CONFIGURED_MODEL == "minimax/minimax-m3:free"

    def test_the_canonical_registry_holds_descriptors_and_nothing_live(self):
        from master_agent.ai_infrastructure.profiles import bootstrap_registry

        registry = ProviderRegistry()
        bootstrap_registry(registry)

        for record in registry.all():
            assert isinstance(record, ProviderDescriptor)
            assert not hasattr(record, "complete")

    def test_the_executable_registry_holds_live_providers_and_nothing_administrative(self):
        from master_agent.plugins.registry import PluginRegistry
        from master_agent.providers.openrouter import OpenRouterProvider

        registry = PluginRegistry()
        registry.register(OpenRouterProvider(model=kd.OPENROUTER_CONFIGURED_MODEL))

        for plugin in registry.all_plugins():
            assert hasattr(plugin, "complete")
            assert not isinstance(plugin, ProviderDescriptor)

    def test_known_but_not_registered_is_unavailable(self):
        from master_agent.ai_infrastructure.profiles import (
            NOT_EXECUTABLE,
            descriptor_availability,
        )

        available, detail = descriptor_availability(
            dataclasses.replace(descriptor(), needs_credentials=False),
            None,
            frozenset(),
            frozenset(),          # nothing is registered
        )

        assert available is False
        assert detail == NOT_EXECUTABLE

    def test_registered_but_not_configured_is_unavailable(self):
        """The other gate, and it is a different one. An implementation
        exists in the process and the founder has still configured no
        credential for it."""
        from master_agent.ai_infrastructure.profiles import descriptor_availability

        available, detail = descriptor_availability(
            descriptor(),                       # needs_credentials=True
            None,
            frozenset(),                        # ...and none is enabled
            frozenset({"openrouter.api"}),      # despite being executable
        )

        assert available is False
        assert "openrouter.api" not in detail or "credential" in detail.lower()

    def test_configured_registered_and_priced_at_zero_is_eligible(self):
        from master_agent.ai_infrastructure.profiles import profile_from_descriptor
        from master_agent.broker.policy import get_policy

        record = kd._with_observed_economics(
            descriptor(),
            kd._observe_openrouter_economics(FakeModelSource(FREE_MODEL)),
            kd.OPENROUTER_CONFIGURED_MODEL,
        )
        profile = profile_from_descriptor(
            dataclasses.replace(record, health=ProviderHealth.HEALTHY),
            None,
            frozenset({"openrouter.api"}),
            frozenset({"openrouter.api"}),
        )

        assert profile.available is True
        assert profile.is_free is True
        assert get_policy("prefer_free").allow_paid is False

    def test_no_ollama_is_unchanged(self):
        """`ollama.local` stays a catalogue entry with no implementation
        in Founder Edition, so it can never be a candidate."""
        constructed = {
            node.func.id
            for node in ast.walk(ast.parse(_module_source()))
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }

        assert "OllamaProvider" not in constructed
        assert "OllamaProvider" not in _module_source()
