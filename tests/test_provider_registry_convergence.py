"""One canonical provider record, and a gateway that cannot cost money.

Two things were true at once and should not have been: `ProviderRegistry`
was the canonical administrative owner, and production authored provider
facts straight from `PROVIDER_CATALOG` without ever consulting it. So the
catalogue stayed a second independent authority for the life of the
process, and anything registered administratively was invisible to
selection.

`openrouter.api` was the other half of the same problem from the opposite
side: a descriptor the Broker could see with nothing behind it that could
be called. KNOWN is not EXECUTABLE.
"""
from __future__ import annotations

import json

import pytest

from master_agent.ai_infrastructure.catalog import PROVIDER_CATALOG
from master_agent.ai_infrastructure.profiles import bootstrap_registry, descriptor_for
from master_agent.broker.registry import (
    EconomicClass,
    ProviderDescriptor,
    ProviderRegistry,
    RegistrationProvenance,
)
from master_agent.providers.openrouter import (
    NO_CREDENTIAL,
    NO_FREE_MODEL,
    OpenRouterProvider,
)
from master_agent.providers.transport import HttpResponse

MODELS = {
    "data": [
        {"id": "paid/expensive", "context_length": 900_000,
         "pricing": {"prompt": "0.001", "completion": "0.002"}},
        {"id": "paid/cheap", "context_length": 800_000,
         "pricing": {"prompt": "0.0000001", "completion": "0"}},
        {"id": "free/small", "context_length": 8_000,
         "pricing": {"prompt": "0", "completion": "0"},
         "architecture": {"input_modalities": ["text"],
                          "output_modalities": ["text"]}},
        {"id": "free/big", "context_length": 256_000,
         "pricing": {"prompt": "0", "completion": "0"},
         "architecture": {"input_modalities": ["text"],
                          "output_modalities": ["text"]}},
        # Bigger than either, free, and not a text reasoner: it emits
        # audio as well as text. It must never be chosen.
        {"id": "vendor/clip-preview", "context_length": 1_048_576,
         "pricing": {"prompt": "0", "completion": "0"},
         "architecture": {"input_modalities": ["text", "image"],
                          "output_modalities": ["text", "audio"]}},
        # The gateway's own aggregator: free, text, and it picks the
        # underlying model itself.
        {"id": "openrouter/free", "context_length": 2_000_000,
         "pricing": {"prompt": "0", "completion": "0"},
         "architecture": {"input_modalities": ["text"],
                          "output_modalities": ["text"]}},
    ]
}


class FakeTransport:
    def __init__(self, models=None, reply="GardenLog\nSproutNote\nPlotPad", status=200):
        self._models = MODELS if models is None else models
        self._reply = reply
        self._status = status
        self.posts: list[tuple] = []

    def get(self, url, timeout, headers=None):
        return HttpResponse(status=200, body=json.dumps(self._models))

    def post_json(self, url, payload, timeout, headers=None):
        self.posts.append((url, payload, headers))
        return HttpResponse(status=self._status, body=json.dumps({
            "choices": [{"message": {"content": self._reply}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 9, "completion_tokens": 7},
        }))


# ---- C: catalogue converges onto the registry --------------------------


class TestTheCatalogueBecomesTheRegistry:

    def test_every_declared_spec_becomes_a_descriptor(self):
        registry = ProviderRegistry()

        imported = bootstrap_registry(registry)

        assert len(imported) == len(PROVIDER_CATALOG)
        assert {d.provider_id for d in registry.all()} == {
            s.provider_id for s in PROVIDER_CATALOG
        }

    def test_the_facts_are_carried_across_not_reinvented(self):
        spec = next(s for s in PROVIDER_CATALOG if s.provider_id == "gemini.api")

        descriptor = descriptor_for(spec)

        assert descriptor.declared_quality == spec.declared_quality
        assert descriptor.latency_ms == spec.latency_ms
        assert descriptor.locality == spec.locality
        assert descriptor.privacy == spec.privacy
        assert descriptor.capabilities == frozenset(spec.capabilities)
        assert descriptor.requires_approval == spec.requires_approval
        assert descriptor.max_context_tokens == spec.max_context_tokens

    def test_nothing_absent_from_the_spec_is_invented(self):
        """A spec that never measured a throughput produces a descriptor
        that has not measured one either."""
        for spec in PROVIDER_CATALOG:
            descriptor = descriptor_for(spec)
            assert descriptor.prefill_tokens_per_second == spec.prefill_tokens_per_second
            assert descriptor.decode_tokens_per_second == spec.decode_tokens_per_second
            assert descriptor.model_load_ms == spec.model_load_ms

    def test_bootstrap_is_idempotent(self):
        registry = ProviderRegistry()

        first = bootstrap_registry(registry)
        second = bootstrap_registry(registry)

        assert len(registry.all()) == len(first)
        assert {d.provider_id for d in first} == {d.provider_id for d in second}

    def test_a_record_with_better_standing_is_not_clobbered(self):
        """A descriptor that was DISCOVERED on this machine outranks a
        declaration. Re-importing the catalogue must not overwrite it."""
        registry = ProviderRegistry()
        spec = PROVIDER_CATALOG[0]
        registry.register(ProviderDescriptor(
            provider_id=spec.provider_id, display_name="found here",
            provider_class="local", provenance=RegistrationProvenance.DISCOVERED,
        ))

        bootstrap_registry(registry)

        kept = registry.get(spec.provider_id)
        assert kept.provenance is RegistrationProvenance.DISCOVERED
        assert kept.display_name == "found here"


class TestEconomicsSaysOnlyWhatIsKnown:

    def test_a_priced_spec_is_paid(self):
        priced = [s for s in PROVIDER_CATALOG if s.cost_per_call > 0]
        assert priced, "the catalogue no longer has a priced provider to check"
        for spec in priced:
            assert descriptor_for(spec).economic_class is EconomicClass.PAID

    def test_zero_cost_is_unknown_not_free(self):
        """`cost_per_call == 0` conflates a recurring free tier, an
        installed subscription and a local runtime. Saying which would be
        inventing a fact the catalogue does not hold."""
        for spec in PROVIDER_CATALOG:
            if spec.cost_per_call == 0.0:
                assert descriptor_for(spec).economic_class is EconomicClass.UNKNOWN

    def test_an_economic_claim_carries_its_source(self):
        for spec in PROVIDER_CATALOG:
            assert descriptor_for(spec).economic_source, (
                "a cost fact with no source is an assertion, not a record"
            )

    def test_no_quota_or_credit_is_ever_guessed(self):
        for spec in PROVIDER_CATALOG:
            descriptor = descriptor_for(spec)
            assert descriptor.quota_remaining is None
            assert descriptor.credit_remaining is None
            assert descriptor.quota_reset_at is None


class TestPersistedDescriptorsCarryNoSecret:

    def test_a_round_trip_preserves_the_economic_record(self):
        registry = ProviderRegistry()
        bootstrap_registry(registry)
        for descriptor in registry.all():
            restored = ProviderDescriptor.from_dict(descriptor.as_dict())
            assert restored.economic_class is descriptor.economic_class
            assert restored.economic_source == descriptor.economic_source

    def test_no_descriptor_field_can_hold_a_credential(self):
        """Checked on FIELD NAMES and on values, never on prose.

        A first version of this grepped the whole blob for `api_key` and
        failed on a `notes` field reading "requires GEMINI_API_KEY" -- a
        description of what the founder must configure, which is exactly
        the kind of thing a descriptor SHOULD say. Naming a credential is
        not carrying one.
        """
        registry = ProviderRegistry()
        bootstrap_registry(registry)

        # Precise names, not loose substrings. A first version matched
        # bare "token" and failed on `max_context_tokens`, which is a
        # capacity, and before that matched "api_key" inside a notes field
        # naming the variable the founder must set. Both were the guard
        # being wrong, not the descriptor.
        secretish = ("api_key", "apikey", "access_token", "auth_token",
                     "secret", "password", "cookie", "authorization",
                     "bearer", "credential")
        for descriptor in registry.all():
            record = descriptor.as_dict()
            for field in record:
                assert not any(s in field.lower() for s in secretish), (
                    f"{descriptor.provider_id} persists a field named {field!r}"
                )
            for field, value in record.items():
                if field == "notes" or not isinstance(value, str):
                    continue
                assert not value.startswith(("sk-", "sk_", "Bearer ")), (
                    f"{descriptor.provider_id}.{field} looks like a credential value"
                )

    def test_the_gateway_credential_never_reaches_a_descriptor(self):
        """The live one: a provider that authenticates with a bearer token
        must keep it in configuration, not in the administrative record."""
        registry = ProviderRegistry()
        bootstrap_registry(registry)

        record = json.dumps(registry.get("openrouter.api").as_dict())

        assert "Bearer" not in record
        assert "OPENROUTER_API_KEY=" not in record

    def test_health_is_not_an_eternal_fact(self):
        """A provider saved healthy yesterday is not healthy today. The
        descriptor may record what was observed; nothing may treat a
        restored value as current."""
        registry = ProviderRegistry()
        bootstrap_registry(registry)
        for descriptor in registry.all():
            assert descriptor.verified_at is None or descriptor.health is not None


# ---- G/H: a gateway that cannot quietly cost money ---------------------


class TestTheOpenRouterGateway:

    def _provider(self, **kwargs):
        kwargs.setdefault("transport", FakeTransport())
        kwargs.setdefault("credential_reader", lambda: "test-credential")
        return OpenRouterProvider(**kwargs)

    def test_only_models_priced_at_exactly_zero_are_eligible(self):
        """`free_models()` is the PRICE filter and nothing else -- what is
        suitable to answer with is `resolve_model()`'s separate question."""
        free = {m["id"] for m in self._provider().free_models()}

        assert free == {
            "free/small", "free/big", "vendor/clip-preview", "openrouter/free",
        }
        assert "paid/cheap" not in free, "a near-zero price is not zero"
        assert "paid/expensive" not in free

    def test_the_model_is_chosen_here_and_sent_explicitly(self):
        """Not `openrouter/auto`, not `openrouter/free` -- both hand the
        choice to the gateway and leave Kalpavriksha recording a decision
        it did not make."""
        transport = FakeTransport()
        provider = self._provider(transport=transport)

        result = provider.complete("three names please")

        _url, payload, _headers = transport.posts[0]
        assert payload["model"] == "free/big"
        assert payload["model"] not in ("openrouter/auto", "openrouter/free")
        assert result.response.model == "free/big"

    def test_the_result_carries_the_evidence_the_call_was_free(self):
        result = self._provider().complete("three names please")

        assert result.detail["pricing_prompt"] == "0"
        assert result.detail["pricing_completion"] == "0"
        assert "models" in result.detail["cost_evidence"]

    def test_no_free_model_means_unavailable_never_a_paid_one(self):
        only_paid = {"data": [MODELS["data"][0], MODELS["data"][1]]}
        provider = self._provider(transport=FakeTransport(models=only_paid))

        result = provider.complete("three names please")

        assert result.ok is False
        assert result.error == NO_FREE_MODEL

    def test_a_missing_credential_is_ordinary_unavailability(self):
        provider = self._provider(credential_reader=lambda: "")

        assert provider.availability().reachable is False
        result = provider.complete("three names please")
        assert result.ok is False
        assert result.error == NO_CREDENTIAL

    def test_the_credential_is_sent_as_a_header_and_never_in_the_payload(self):
        transport = FakeTransport()
        self._provider(transport=transport).complete("three names please")

        _url, payload, headers = transport.posts[0]
        assert headers["Authorization"].startswith("Bearer ")
        assert "test-credential" not in json.dumps(payload)

    def test_constructing_it_touches_nothing(self):
        """Registration must never cause a network call or read a
        credential -- the same discipline the Gemini provider holds."""
        calls = []

        class Loud:
            def get(self, *a, **k):
                calls.append("get")
                raise AssertionError("constructed provider hit the network")

            def post_json(self, *a, **k):
                calls.append("post")
                raise AssertionError("constructed provider hit the network")

        def loud_credential():
            calls.append("credential")
            return "x"

        OpenRouterProvider(transport=Loud(), credential_reader=loud_credential)

        assert calls == []


class TestKnownIsNotExecutable:

    def test_a_descriptor_alone_does_not_make_a_provider_callable(self):
        """`openrouter.api` sat in provider knowledge for a long time with
        nothing behind it. A registry entry is an administrative record,
        not an execution binding."""
        registry = ProviderRegistry()
        bootstrap_registry(registry)

        descriptor = registry.get("openrouter.api")

        assert descriptor is not None, "the catalogue still declares it"
        assert not descriptor.execution_capability, (
            "a descriptor claiming an execution binding must have one that exists"
        )


class TestTheModelChoiceStaysHere:

    def _provider(self):
        return OpenRouterProvider(
            transport=FakeTransport(), credential_reader=lambda: "test-credential"
        )

    def test_a_model_that_emits_more_than_text_is_never_chosen(self):
        """Live, an earlier filter accepted a clip-generation model --
        `['text','image'] -> ['text','audio']` -- because text was
        *included* in its outputs, and chose it to answer a three-name
        question. A text reasoner emits text and nothing else."""
        chosen = self._provider().resolve_model()

        assert chosen["id"] != "vendor/clip-preview"
        assert chosen["id"] == "free/big"

    def test_the_gateways_own_aggregator_is_never_chosen(self):
        """`openrouter/free` is free, is text, and has the largest context
        of all of them -- and it picks the underlying model itself, which
        is the decision this provider exists to keep."""
        provider = self._provider()

        chosen = provider.resolve_model()

        assert chosen["id"] != "openrouter/free"
        assert "openrouter/free" in {m["id"] for m in provider.free_models()}, (
            "the aggregator is still offered by the gateway; it is excluded "
            "by choice, not by absence"
        )

    def test_the_choice_is_deterministic(self):
        provider = self._provider()

        assert provider.resolve_model()["id"] == provider.resolve_model()["id"]
