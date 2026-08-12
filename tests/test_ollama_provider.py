"""Mission Brief 033 — the Ollama provider, Kalpavriksha's first real AI
execution path.

Everything here runs against a scripted transport. That is not a
compromise: the property under test is *what this provider does with what
the daemon says*, and a test that needed a live model would test the model
instead — slowly, and differently on every machine. The live proof that
the transport itself works is a founder-facing run recorded in
`docs/MISSION_BRIEF_033.md`, not a unit test.

The forbidden list is asserted rather than trusted, as MB031 and MB032 did
before it: no decision-making in a provider, no network outside the one
module that owns it, no second door to the machine.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from master_agent.plugins.base import ModelProvider, RiskTier
from master_agent.providers import ollama as ollama_module
from master_agent.providers import response as response_module
from master_agent.providers.ollama import (
    GENERATE_PATH,
    OLLAMA_PROVIDER_ID,
    TAGS_PATH,
    OllamaProvider,
    ProviderExecutionFailed,
    _count,
)
from master_agent.providers.response import (
    FAILURES,
    MALFORMED,
    OUTCOMES,
    REJECTED,
    SUCCEEDED,
    TIMED_OUT,
    UNAVAILABLE,
    Availability,
    ProviderResponse,
    ProviderResult,
    failure,
)
from master_agent.providers.transport import (
    HttpResponse,
    Transport,
    TransportTimeout,
    TransportUnavailable,
    UrllibTransport,
)
from tests.broker_test_support import (
    FakeTransport,
    ollama,
    ollama_body,
    tags_body,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = REPO_ROOT / "src" / "master_agent" / "providers"
MODULES = sorted(PACKAGE_DIR.glob("*.py"))


def ok(**kwargs) -> HttpResponse:
    return HttpResponse(200, ollama_body(**kwargs))


# =========================================================================
# The response vocabulary
# =========================================================================


def test_every_outcome_is_either_success_or_a_named_failure():
    assert set(OUTCOMES) == {SUCCEEDED, *FAILURES}


def test_success_is_not_a_failure():
    assert SUCCEEDED not in FAILURES


@pytest.mark.parametrize("outcome", FAILURES)
def test_a_failure_is_never_ok(outcome):
    assert failure("p", outcome, "why").ok is False


def test_a_success_is_ok():
    result = ProviderResult("p", SUCCEEDED, ProviderResponse(text="hi"))

    assert result.ok is True
    assert result.text == "hi"


def test_a_failed_result_has_no_text_rather_than_an_apology_as_text():
    """A caller that cannot tell an answer from an error message will
    store the error message as an answer."""
    assert failure("p", UNAVAILABLE, "daemon is down").text == ""


def test_tokens_are_summed_only_when_both_halves_were_reported():
    assert ProviderResponse("x", prompt_tokens=10, completion_tokens=5).total_tokens == 15


@pytest.mark.parametrize(
    ("prompt", "completion"), [(None, 5), (10, None), (None, None)]
)
def test_an_unreported_token_count_never_becomes_a_number(prompt, completion):
    """A zero that means "unreported" would make every future average
    wrong, quietly (ADR-0016)."""
    response = ProviderResponse("x", prompt_tokens=prompt, completion_tokens=completion)

    assert response.total_tokens is None


def test_a_response_serialises_for_the_record():
    payload = ProviderResponse("hi", model="m", latency_ms=12.0, prompt_tokens=1,
                               completion_tokens=2).as_dict()

    assert payload["text"] == "hi"
    assert payload["total_tokens"] == 3


def test_a_result_serialises_with_its_response():
    payload = ProviderResult("p", SUCCEEDED, ProviderResponse("hi")).as_dict()

    assert payload["ok"] is True
    assert payload["response"]["text"] == "hi"


def test_a_failed_result_serialises_without_one():
    payload = failure("p", TIMED_OUT, "too slow", timeout_seconds=5).as_dict()

    assert payload["response"] is None
    assert payload["detail"]["timeout_seconds"] == 5


def test_a_failure_helper_defaults_to_one_attempt():
    assert failure("p", UNAVAILABLE, "x").attempts == 1


# ---- availability -------------------------------------------------------


@pytest.mark.parametrize(
    ("held", "wanted"),
    [
        ("gemma4:latest", "gemma4:latest"),
        ("gemma4:latest", "gemma4"),
        ("gemma4", "gemma4:latest"),
        ("hermes3:8b", "hermes3"),
    ],
)
def test_a_model_is_recognised_however_the_tag_is_written(held, wanted):
    """A founder writing `gemma4` and a daemon reporting `gemma4:latest`
    mean the same thing, and refusing to run because of a suffix would be
    the pedantry that makes tools annoying."""
    assert Availability("p", True, models=(held,)).has(wanted) is True


def test_a_model_that_is_not_there_is_not_there():
    assert Availability("p", True, models=("a", "b")).has("c") is False


@pytest.mark.parametrize("wanted", ["", "   ", None])
def test_asking_whether_nothing_is_installed_is_always_no(wanted):
    assert Availability("p", True, models=("a",)).has(wanted) is False


def test_availability_serialises():
    payload = Availability("p", True, models=("a",), detail="reachable").as_dict()

    assert payload == {
        "provider_id": "p",
        "reachable": True,
        "models": ["a"],
        "detail": "reachable",
    }


# =========================================================================
# Identity and the Plugin contract
# =========================================================================


def test_the_provider_id_matches_the_broker_catalogue():
    """Two vocabularies, kept in step by a test rather than by one package
    importing the other. `providers/` sits below the wiring layer and must
    not depend on it."""
    from master_agent.ai_infrastructure.catalog import find

    assert find(OLLAMA_PROVIDER_ID) is not None


def test_the_manifest_is_named_for_the_provider_id():
    """So the Broker's answer resolves straight to this object through the
    registry, with no translation table in between."""
    assert ollama().manifest.name == OLLAMA_PROVIDER_ID


def test_the_manifest_offers_exactly_one_capability():
    capabilities = ollama().manifest.capabilities

    assert len(capabilities) == 1
    assert capabilities[0].name == ModelProvider.CAPABILITY_NAME


def test_generation_is_classified_read_only():
    """Generating text reads and returns text. Anything it *recommends*
    still needs its own capability and its own tier."""
    assert ollama().manifest.capabilities[0].risk_tier is RiskTier.READ_ONLY


def test_the_manifest_names_the_model_it_would_run():
    assert "test-model" in ollama().manifest.capabilities[0].description


def test_the_provider_reports_what_it_was_configured_with():
    provider = ollama(model="m", base_url="http://host:1234/")

    assert provider.model == "m"
    assert provider.base_url == "http://host:1234", "a trailing slash is trimmed once"
    assert provider.provider_id == OLLAMA_PROVIDER_ID


def test_a_provider_is_a_model_provider():
    assert isinstance(ollama(), ModelProvider)


def test_the_adapter_exposes_no_retry_configuration_at_all():
    """MB038: retry belongs to the layer that owns the failure's meaning.
    A refused connection means nothing to an adapter, so there is nothing
    here to configure -- and no constant left to quietly raise."""
    import inspect

    from master_agent.providers import ollama as module

    parameters = inspect.signature(OllamaProvider.__init__).parameters
    assert "max_attempts" not in parameters
    assert "retry_delay_seconds" not in parameters
    assert "sleep" not in parameters
    assert not hasattr(module, "DEFAULT_MAX_ATTEMPTS")
    assert not hasattr(module, "DEFAULT_RETRY_DELAY_SECONDS")


# =========================================================================
# A successful execution
# =========================================================================


def test_a_prompt_reaches_the_generate_endpoint():
    provider = ollama(base_url="http://host:11434")

    provider.complete("say hi")
    url, payload, _timeout = provider._transport.posts[0]

    assert url == f"http://host:11434{GENERATE_PATH}"
    assert payload["prompt"] == "say hi"


def test_streaming_is_off_because_this_returns_one_answer():
    provider = ollama()
    provider.complete("hi")

    assert provider._transport.posts[0][1]["stream"] is False


def test_the_configured_model_is_what_is_asked_for():
    provider = ollama(model="chosen-by-configuration")
    provider.complete("hi")

    assert provider._transport.posts[0][1]["model"] == "chosen-by-configuration"


def test_the_configured_timeout_is_what_is_waited():
    provider = ollama(timeout_seconds=7.5)
    provider.complete("hi")

    assert provider._transport.posts[0][2] == 7.5


def test_a_successful_call_returns_the_text():
    assert ollama(ok(text="the answer")).complete("q").text == "the answer"


def test_a_successful_call_reports_the_model_that_answered():
    """The model that ran, not the model that was asked for -- a daemon
    resolving `gemma4` to `gemma4:latest` is information worth keeping."""
    result = ollama(ok(model="gemma4:latest"), model="gemma4").complete("q")

    assert result.response.model == "gemma4:latest"


def test_token_counts_are_read_from_the_daemon():
    result = ollama(ok(prompt_tokens=23, completion_tokens=2)).complete("q")

    assert result.response.prompt_tokens == 23
    assert result.response.completion_tokens == 2
    assert result.response.total_tokens == 25


def test_a_daemon_that_reports_no_tokens_leaves_them_unknown():
    result = ollama(ok(prompt_tokens=None, completion_tokens=None)).complete("q")

    assert result.response.prompt_tokens is None
    assert result.response.total_tokens is None


def test_the_finish_reason_is_kept():
    result = ollama(ok(done_reason="length")).complete("q")

    assert result.response.finish_reason == "length"


def test_latency_is_measured_from_an_injected_clock():
    """Monotonic and injected, so a latency is not a fact about how busy
    the test machine was."""
    provider = ollama(step_seconds=0.5)

    assert provider.complete("q").latency_ms == 500.0


def test_a_first_time_success_reports_one_attempt_and_no_retries():
    result = ollama().complete("q")

    assert result.attempts == 1


def test_an_empty_answer_is_still_an_answer():
    """A model that returns nothing has answered with nothing. Inventing
    an error here would be inventing a fact."""
    result = ollama(ok(text="")).complete("q")

    assert result.ok is True
    assert result.text == ""


def test_context_is_appended_as_labelled_lines():
    provider = ollama()
    provider.complete("summarise", {"file": "notes.md", "author": "founder"})

    prompt = provider._transport.posts[0][1]["prompt"]

    assert prompt.startswith("summarise")
    assert "file: notes.md" in prompt
    assert "author: founder" in prompt


def test_context_is_ordered_so_the_same_call_builds_the_same_prompt():
    """Otherwise two identical requests would hash differently and the
    Prompt Cache could never match them."""
    first, second = ollama(), ollama()
    first.complete("q", {"b": 2, "a": 1})
    second.complete("q", {"a": 1, "b": 2})

    assert first._transport.posts[0][1]["prompt"] == second._transport.posts[0][1]["prompt"]


def test_no_context_leaves_the_prompt_exactly_as_written():
    provider = ollama()
    provider.complete("just this")

    assert provider._transport.posts[0][1]["prompt"] == "just this"


def test_options_are_forwarded_when_given():
    provider = ollama(options={"temperature": 0})
    provider.complete("q")

    assert provider._transport.posts[0][1]["options"] == {"temperature": 0}


def test_per_call_options_override_configured_ones():
    provider = ollama(options={"temperature": 0, "seed": 1})
    provider.complete("q", options={"temperature": 1})

    sent = provider._transport.posts[0][1]["options"]

    assert sent == {"temperature": 1, "seed": 1}


def test_no_options_key_is_sent_when_there_are_none():
    """An empty options object is not the same as no options, and some
    daemons treat it differently."""
    provider = ollama()
    provider.complete("q")

    assert "options" not in provider._transport.posts[0][1]


# =========================================================================
# Failures — each one a fact a founder can act on (Rule 5)
# =========================================================================


def test_a_daemon_that_is_not_running_is_reported_as_unavailable():
    provider = ollama(TransportUnavailable("connection refused"))

    result = provider.complete("q")

    assert result.outcome == UNAVAILABLE
    assert "connection refused" in result.error


def test_the_unavailable_message_says_where_it_looked():
    """Because the fix is almost always "start Ollama" or "you changed the
    port"."""
    provider = ollama(
        TransportUnavailable("refused"), base_url="http://host:9999"
    )

    result = provider.complete("q")

    assert "http://host:9999" in result.error
    assert result.detail["url"] == "http://host:9999"


def test_a_timeout_is_its_own_outcome():
    """Distinct from unavailable: something *is* listening, and the answer
    for the founder is different (raise the timeout, or use a smaller
    model)."""
    provider = ollama(TransportTimeout("no answer within 30s"))

    result = provider.complete("q")

    assert result.outcome == TIMED_OUT
    assert result.detail["timeout_seconds"] == 30.0


def test_a_timeout_is_never_retried():
    """Asking again is how a 120-second wait becomes a 240-second one for
    the same answer."""
    provider = ollama(TransportTimeout("slow"), TransportTimeout("slow"))

    result = provider.complete("q")

    assert result.attempts == 1
    assert len(provider._transport.posts) == 1


def test_a_connection_failure_is_not_retried_either():
    """MB038 removed the one retry this adapter had. A refused socket is
    sometimes a daemon still starting -- and deciding whether that is
    worth another go is the Runtime's call, not the adapter's, because
    only the Runtime knows what the work was for."""
    provider = ollama(TransportUnavailable("refused"), ok(text="second time"))

    result = provider.complete("q")

    assert result.outcome == UNAVAILABLE
    assert result.attempts == 1
    assert len(provider._transport.posts) == 1, "the adapter tried again"


def test_a_repeated_connection_failure_reports_the_first_one():
    provider = ollama(
        TransportUnavailable("a"),
        TransportUnavailable("b"),
        TransportUnavailable("c"),
    )

    result = provider.complete("q")

    assert result.outcome == UNAVAILABLE
    assert result.attempts == 1


def test_no_sleep_is_reachable_from_the_adapter():
    """There is no retry, so there is nothing to wait between. An adapter
    that could sleep could quietly reintroduce one."""
    import ast
    import inspect

    source = inspect.getsource(OllamaProvider)
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Attribute):
            assert node.attr != "sleep", "the adapter can still sleep"


def test_latency_covers_every_attempt_including_the_failed_ones():
    """It is what the founder actually waited."""
    provider = ollama(TransportUnavailable("refused"), ok(), step_seconds=0.4)

    assert provider.complete("q").latency_ms == 400.0


@pytest.mark.parametrize("status", [400, 404, 500, 503])
def test_an_http_error_is_a_rejection_not_an_outage(status):
    """The provider is *there*. Conflating "it said no" with "it is not
    running" would send the founder to fix the wrong thing."""
    provider = ollama(HttpResponse(status, json.dumps({"error": "nope"})))

    result = provider.complete("q")

    assert result.outcome == REJECTED
    assert result.detail["status"] == status


def test_a_rejection_keeps_the_reason_the_daemon_gave():
    """Ollama puts "model X not found" in the body, and dropping it in
    favour of "HTTP 404" throws away the only useful half."""
    provider = ollama(
        HttpResponse(404, json.dumps({"error": 'model "hermes3" not found'}))
    )

    result = provider.complete("q")

    assert 'model "hermes3" not found' in result.error


def test_a_rejection_lists_the_models_that_are_installed():
    """The single most useful thing to know when the configured model is
    not there."""
    provider = ollama(
        HttpResponse(404, json.dumps({"error": "not found"})),
        model="missing",
        tags=HttpResponse(200, tags_body("gemma4:latest", "hermes3")),
    )

    result = provider.complete("q")

    assert result.detail["installed"] == ["gemma4:latest", "hermes3"]
    assert result.detail["model"] == "missing"


def test_a_rejection_with_an_unreadable_body_still_reports_the_status():
    provider = ollama(HttpResponse(500, "<html>gateway</html>"))

    result = provider.complete("q")

    assert result.outcome == REJECTED
    assert "HTTP 500" in result.error


def test_a_rejection_with_an_empty_body_says_only_the_status():
    provider = ollama(HttpResponse(503, ""))

    assert ollama_error(provider) == "HTTP 503"


def ollama_error(provider) -> str:
    return provider.complete("q").error


def test_a_body_that_is_not_json_is_malformed():
    provider = ollama(HttpResponse(200, "not json at all"))

    result = provider.complete("q")

    assert result.outcome == MALFORMED
    assert "not JSON" in result.error


def test_json_without_a_response_field_is_malformed():
    """It answered in the right shape's clothing. Reading `.get("response",
    "")` here would turn a broken daemon into a silent empty answer."""
    provider = ollama(HttpResponse(200, json.dumps({"model": "m", "done": True})))

    result = provider.complete("q")

    assert result.outcome == MALFORMED
    assert "no 'response' field" in result.error


def test_json_that_is_not_an_object_is_malformed():
    provider = ollama(HttpResponse(200, json.dumps(["a", "list"])))

    assert provider.complete("q").outcome == MALFORMED


def test_a_malformed_body_is_kept_in_the_detail_for_diagnosis():
    provider = ollama(HttpResponse(200, "wat"))

    assert provider.complete("q").detail["body"] == "wat"


def test_a_malformed_body_is_truncated_rather_than_pasted_whole():
    provider = ollama(HttpResponse(200, "x" * 5000))

    assert len(provider.complete("q").detail["body"]) == 200


@pytest.mark.parametrize("outcome", [UNAVAILABLE, TIMED_OUT, MALFORMED, REJECTED])
def test_no_failure_ever_produces_a_response_object(outcome):
    """`response` is set exactly when the outcome is success. A caller
    that has to check both will eventually check neither."""
    scripts = {
        UNAVAILABLE: TransportUnavailable("x"),
        TIMED_OUT: TransportTimeout("x"),
        MALFORMED: HttpResponse(200, "junk"),
        REJECTED: HttpResponse(500, ""),
    }
    provider = ollama(scripts[outcome])

    assert provider.complete("q").response is None


def test_a_failure_never_raises():
    """Rule 5: a failure is an answer. An exception here would make every
    caller wrap every call, and one of them would wrap it with a
    fallback."""
    provider = ollama(TransportUnavailable("down"))

    assert provider.complete("q").ok is False


# =========================================================================
# Availability probing
# =========================================================================


def test_availability_reports_the_models_the_daemon_holds():
    provider = ollama(tags=HttpResponse(200, tags_body("a", "b")))

    availability = provider.availability()

    assert availability.reachable is True
    assert availability.models == ("a", "b")


def test_availability_asks_the_tags_endpoint():
    provider = ollama(base_url="http://host:1")
    provider.availability()

    assert provider._transport.gets[0][0] == f"http://host:1{TAGS_PATH}"


def test_a_daemon_that_is_down_is_not_reachable():
    provider = ollama(tags=TransportUnavailable("refused"))

    availability = provider.availability()

    assert availability.reachable is False
    assert "refused" in availability.detail


def test_a_daemon_that_times_out_is_not_reachable():
    provider = ollama(tags=TransportTimeout("slow"))

    assert provider.availability().reachable is False


def test_an_http_error_on_tags_is_not_reachable():
    provider = ollama(tags=HttpResponse(500, ""))

    availability = provider.availability()

    assert availability.reachable is False
    assert "HTTP 500" in availability.detail


def test_an_unreadable_tags_body_is_not_reachable():
    provider = ollama(tags=HttpResponse(200, "not json"))

    availability = provider.availability()

    assert availability.reachable is False
    assert "unreadable" in availability.detail


def test_a_tags_body_with_no_models_reports_none_rather_than_failing():
    provider = ollama(tags=HttpResponse(200, json.dumps({"models": []})))

    availability = provider.availability()

    assert availability.reachable is True
    assert availability.models == ()


def test_nameless_entries_in_the_tags_list_are_skipped():
    provider = ollama(
        tags=HttpResponse(200, json.dumps({"models": [{"name": "a"}, {}, "junk"]}))
    )

    assert provider.availability().models == ("a",)


def test_availability_never_ranks_what_it_finds():
    """A list is not a shortlist. The order is the daemon's."""
    provider = ollama(tags=HttpResponse(200, tags_body("zebra", "alpha")))

    assert provider.availability().models == ("zebra", "alpha")


# =========================================================================
# The frozen ModelProvider contract
# =========================================================================


def test_generate_returns_the_text():
    assert ollama(ok(text="hello")).generate("q") == "hello"


def test_generate_raises_rather_than_returning_an_error_as_text():
    """The one failure mode that would poison everything downstream."""
    provider = ollama(TransportUnavailable("down"))

    with pytest.raises(ProviderExecutionFailed) as raised:
        provider.generate("q")

    assert raised.value.result.outcome == UNAVAILABLE


def test_the_raised_failure_carries_the_whole_result():
    provider = ollama(HttpResponse(404, json.dumps({"error": "no model"})))

    with pytest.raises(ProviderExecutionFailed) as raised:
        provider.generate("q")

    assert raised.value.result.detail["status"] == 404


def test_generate_forwards_context():
    provider = ollama()
    provider.generate("q", {"k": "v"})

    assert "k: v" in provider._transport.posts[0][1]["prompt"]


def test_invoke_still_satisfies_the_plugin_contract():
    """`ModelProvider.invoke` predates all of this and is frozen. A
    provider that broke it would stop being a Plugin."""
    result = ollama(ok(text="hi")).invoke("generate_text", {"prompt": "q"})

    assert result.success is True
    assert result.output == "hi"


def test_invoke_reports_a_failure_rather_than_raising():
    provider = ollama(TransportUnavailable("down"))

    result = provider.invoke("generate_text", {"prompt": "q"})

    assert result.success is False
    assert "unavailable" in result.error


def test_invoke_refuses_an_unknown_capability():
    assert ollama().invoke("do_something_else", {}).success is False


# ---- the token counter --------------------------------------------------


@pytest.mark.parametrize("value", [0, 1, 4096])
def test_a_reported_count_is_kept(value):
    assert _count(value) == value


@pytest.mark.parametrize("value", [None, "12", 1.5, -1, True, False, [], {}])
def test_anything_that_is_not_a_count_is_unknown(value):
    """`True` is an `int` in Python, and a token count of True would be a
    1 that nobody could explain."""
    assert _count(value) is None


# =========================================================================
# The transport
# =========================================================================


def test_a_response_knows_whether_it_was_ok():
    assert HttpResponse(200, "").ok is True
    assert HttpResponse(299, "").ok is True
    assert HttpResponse(300, "").ok is False
    assert HttpResponse(404, "").ok is False


def test_a_response_parses_its_own_json():
    assert HttpResponse(200, '{"a": 1}').json() == {"a": 1}


def test_a_response_that_is_not_json_raises_rather_than_guessing():
    with pytest.raises(ValueError):
        HttpResponse(200, "nope").json()


def test_the_real_transport_satisfies_the_protocol():
    assert isinstance(UrllibTransport(), Transport)


def test_a_fake_transport_satisfies_the_protocol():
    """Which is what makes every test above a test of the real code
    path."""
    assert isinstance(FakeTransport(), Transport)


@pytest.mark.parametrize("scheme", ["file", "ftp", "gopher", "data"])
def test_the_transport_refuses_a_non_http_url(scheme):
    """`urlopen` will happily open `file://`. A provider base URL is
    configuration, and configuration that can read the disk through an
    HTTP client is a hole nobody would look for."""
    with pytest.raises(TransportUnavailable):
        UrllibTransport().get(f"{scheme}:///etc/passwd", timeout=1)


def test_the_transport_refuses_a_non_http_post():
    with pytest.raises(TransportUnavailable):
        UrllibTransport().post_json("file:///tmp/x", {}, timeout=1)


class FakeHandle:
    """What `urlopen` hands back on success, as a context manager."""

    def __init__(self, status: int = 200, body: bytes = b'{"ok": true}') -> None:
        self.status = status
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *_exc: object) -> None:
        return None


def patched_urlopen(monkeypatch, behaviour):
    """Replace the one stdlib call this module makes.

    Faking `urlopen` rather than standing up a server is the right level:
    what is under test is the *translation* of a stdlib exception into one
    of exactly two transport failures, and a real server cannot produce
    most of them on demand.
    """
    import urllib.request

    def fake(request, timeout=None):
        if isinstance(behaviour, BaseException):
            raise behaviour
        return behaviour

    monkeypatch.setattr(urllib.request, "urlopen", fake)


def test_a_successful_request_is_read_into_a_response(monkeypatch):
    patched_urlopen(monkeypatch, FakeHandle(200, b'{"response": "hi"}'))

    response = UrllibTransport().get("http://host/x", timeout=1)

    assert response.status == 200
    assert response.json() == {"response": "hi"}


def test_a_post_sends_json_and_reads_the_answer(monkeypatch):
    patched_urlopen(monkeypatch, FakeHandle(200, b"{}"))

    assert UrllibTransport().post_json("http://host/x", {"a": 1}, timeout=1).ok


def test_a_body_that_is_not_utf8_is_replaced_rather_than_fatal(monkeypatch):
    """A daemon that answers with broken bytes is a daemon that answered.
    Losing the whole response to a decode error would turn a readable
    failure into an unreadable one."""
    patched_urlopen(monkeypatch, FakeHandle(200, b"\xff\xfe not utf8"))

    assert UrllibTransport().get("http://host/x", timeout=1).body


def test_an_http_error_becomes_a_response_not_an_exception(monkeypatch):
    """A 404 is an answer: "that model is not installed" arrives as one,
    and turning it into an exception would lose the body that says so."""
    import io
    import urllib.error

    patched_urlopen(
        monkeypatch,
        urllib.error.HTTPError(
            "http://host/x", 404, "Not Found", {}, io.BytesIO(b'{"error": "no model"}')
        ),
    )

    response = UrllibTransport().get("http://host/x", timeout=1)

    assert response.status == 404
    assert response.json() == {"error": "no model"}


def test_an_http_error_with_an_unreadable_body_still_reports_the_status(monkeypatch):
    import urllib.error

    patched_urlopen(
        monkeypatch, urllib.error.HTTPError("http://host/x", 500, "Boom", {}, None)
    )

    response = UrllibTransport().get("http://host/x", timeout=1)

    assert response.status == 500
    assert response.body == ""


def test_an_http_error_whose_body_cannot_be_read_still_reports_the_status(monkeypatch):
    """A body we cannot read is no body. Losing the status code as well
    would leave the founder with nothing at all."""
    import io
    import urllib.error

    class Unreadable(io.BytesIO):
        def read(self, *_args):
            raise OSError("connection reset while reading the body")

    patched_urlopen(
        monkeypatch,
        urllib.error.HTTPError("http://host/x", 502, "Bad Gateway", {}, Unreadable()),
    )

    response = UrllibTransport().get("http://host/x", timeout=1)

    assert response.status == 502
    assert response.body == ""


def test_a_bare_timeout_becomes_a_transport_timeout(monkeypatch):
    patched_urlopen(monkeypatch, TimeoutError("timed out"))

    with pytest.raises(TransportTimeout):
        UrllibTransport().get("http://host/x", timeout=2)


def test_a_url_error_wrapping_a_timeout_is_still_a_timeout(monkeypatch):
    """`urllib` wraps a socket timeout in a `URLError`, and reading it as
    "unavailable" would send the founder to restart a daemon that is
    running perfectly well."""
    import urllib.error

    patched_urlopen(monkeypatch, urllib.error.URLError(TimeoutError("slow")))

    with pytest.raises(TransportTimeout):
        UrllibTransport().get("http://host/x", timeout=2)


def test_a_url_error_is_otherwise_unavailable(monkeypatch):
    import urllib.error

    patched_urlopen(monkeypatch, urllib.error.URLError("connection refused"))

    with pytest.raises(TransportUnavailable) as raised:
        UrllibTransport().get("http://host/x", timeout=1)

    assert "refused" in str(raised.value)


def test_any_other_os_error_is_unavailable(monkeypatch):
    """A DNS failure, a broken pipe, an exhausted file table -- all of
    them mean the same thing to a caller: it did not get through."""
    patched_urlopen(monkeypatch, OSError("no route to host"))

    with pytest.raises(TransportUnavailable):
        UrllibTransport().get("http://host/x", timeout=1)


def test_the_timeout_reaches_the_message_a_founder_reads(monkeypatch):
    patched_urlopen(monkeypatch, TimeoutError())

    with pytest.raises(TransportTimeout) as raised:
        UrllibTransport().get("http://host/x", timeout=42)

    assert "42s" in str(raised.value)


def test_a_connection_to_nothing_becomes_a_transport_error():
    """A real socket call, to a port nothing is on. The one test here that
    touches the network stack, and it touches it to prove that a dead
    endpoint never escapes as a raw `URLError`.

    Asserted against the *base* type on purpose: whether a dead port
    refuses or silently drops is the operating system's choice, so
    demanding `TransportUnavailable` specifically would be a test of
    Windows rather than of this code. What matters is that both arrive as
    something the provider knows how to turn into a result.
    """
    from master_agent.providers.transport import TransportError

    with pytest.raises(TransportError):
        UrllibTransport().get("http://127.0.0.1:9/nothing", timeout=1)


# =========================================================================
# Architecture purity
# =========================================================================

FORBIDDEN_ELSEWHERE = ("urllib", "socket", "http.client", "httpx", "requests")


def _imported(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


@pytest.mark.parametrize(
    "path", [p for p in MODULES if p.name != "transport.py"], ids=lambda p: p.name
)
def test_only_the_transport_module_touches_the_network(path):
    """One door, the same discipline `desktop/probe.py` has for subprocess
    and `store.py` has for the filesystem. A second HTTP client somewhere
    in this package is how a timeout policy silently stops applying."""
    for name in _imported(path):
        for forbidden in FORBIDDEN_ELSEWHERE:
            assert not name.startswith(forbidden), f"{path.name} imports {name}"


@pytest.mark.parametrize("path", MODULES, ids=lambda p: p.name)
def test_no_provider_module_spawns_a_process(path):
    for name in _imported(path):
        assert not name.startswith("subprocess")
        assert not name.startswith("os.system")


@pytest.mark.parametrize("path", MODULES, ids=lambda p: p.name)
def test_a_provider_never_reaches_the_layer_that_decides(path):
    """Rule 4, structurally. A provider that could see the Broker, the
    ledger, or the policy would eventually consult one."""
    for name in _imported(path):
        assert not name.startswith("master_agent.broker")
        assert not name.startswith("master_agent.ai_infrastructure")
        assert not name.startswith("master_agent.mission_control")
        assert not name.startswith("master_agent.runtime")


@pytest.mark.parametrize(
    "forbidden", ["select", "rank", "score", "choose", "prefer", "fallback"]
)
def test_a_provider_defines_no_decision_making_function(forbidden):
    """MB033 Rule 4: it executes, it never decides. Checked by AST on
    function names rather than by grepping the file, so the docstrings
    that *explain* the rule do not break it."""
    for path in MODULES:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                assert forbidden not in node.name.lower(), (
                    f"{path.name} defines {node.name}()"
                )


@pytest.mark.parametrize(
    "forbidden", ["def install", "def download", "def benchmark", "def upgrade"]
)
def test_a_provider_never_mutates_the_ecosystem(forbidden):
    """ADR-0018 Decision 6 puts install/remove/upgrade behind an
    `IRREVERSIBLE` founder decision, in an Executive that does not exist
    yet. Not here, and not by accident."""
    for path in MODULES:
        assert forbidden not in path.read_text(encoding="utf-8")


def test_the_package_root_imports_nothing():
    """Importing `master_agent.providers` must not pull in a network
    client, which is what lets the AI Infrastructure layer import the
    response vocabulary without acquiring the ability to make a request."""
    tree = ast.parse((PACKAGE_DIR / "__init__.py").read_text(encoding="utf-8"))
    imports = [n for n in ast.walk(tree) if isinstance(n, ast.Import | ast.ImportFrom)]

    assert imports == []


def test_the_response_vocabulary_is_pure_data():
    """It is the module the wiring layer imports, so it must stay free of
    anything that could execute."""
    for name in _imported(PACKAGE_DIR / "response.py"):
        assert name in ("__future__", "dataclasses", "typing"), name


def test_the_provider_holds_no_retry_policy_below_itself():
    """"No retries beyond its own transport layer" (Rule 4) is only true
    if the transport does not have one of its own."""
    text = (PACKAGE_DIR / "transport.py").read_text(encoding="utf-8")

    assert "attempt" not in text.lower().replace("attempts", "").replace("attempted", "")
    assert "retry" not in text.lower() or "No retry policy lives here" in text


def test_every_module_says_which_brief_it_serves():
    for path in MODULES:
        head = " ".join(path.read_text(encoding="utf-8")[:600].split())
        # MB038 added `budget.py` here. A newer brief is a valid answer to
        # "which brief does this serve"; the convention is that the answer
        # exists, not that it is always 033. `gemini.py` (Build 2, Founder
        # decision: provider search closed) is not a numbered Mission
        # Brief, so it states its own identity instead.
        assert any(
            marker in head
            for marker in (
                "Mission Brief 033",
                "Mission Brief 038",
                "Gemini API Provider",
            )
        ), path.name


def test_the_response_module_names_no_vendor():
    """The vocabulary is shared by every future provider. A vendor name in
    it would make the next one awkward."""
    text = response_module.__doc__ or ""
    for vendor in ("openai", "anthropic", "claude", "gemini", "qwen"):
        assert vendor not in text.lower()


def _code_identifiers(path: Path) -> set[str]:
    """Every name and string literal in a module *except* its docstrings.

    Prose has to be able to say "Ollama being down" while explaining what
    a failure means; code must not depend on it. Grepping the file cannot
    tell those apart, and the first version of the test below failed on
    its own explanation — the same mistake MB032 made and fixed twice.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    docstrings = {
        id(node.body[0].value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef)
        and node.body
        and isinstance(node.body[0], ast.Expr)
        and isinstance(node.body[0].value, ast.Constant)
        and isinstance(node.body[0].value.value, str)
    }
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if id(node) not in docstrings:
                found.add(node.value.lower())
        elif isinstance(node, ast.Name):
            found.add(node.id.lower())
        elif isinstance(node, ast.Attribute):
            found.add(node.attr.lower())
        elif isinstance(
            node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef | ast.alias
        ):
            found.add(node.name.lower())
    return found


def test_the_ollama_module_is_the_only_one_whose_code_names_ollama():
    """Provider identity is contained, exactly as MB032 contained it to
    one catalogue file. Checked against code, never prose — see
    `_code_identifiers`."""
    for path in MODULES:
        if path.name == "ollama.py":
            continue
        for name in _code_identifiers(path):
            assert "ollama" not in name, f"{path.name} names ollama in code: {name!r}"


def test_the_package_root_names_a_vendor_only_in_prose():
    """The exemption above, pinned: `__init__.py` has no code at all, so
    the name can only be in the docstring."""
    body = (PACKAGE_DIR / "__init__.py").read_text(encoding="utf-8")
    tree = ast.parse(body)

    assert [type(node).__name__ for node in tree.body] == ["Expr"], "root has code"


def test_the_module_docstring_states_the_rule_it_is_built_around():
    assert "never decides" in (ollama_module.__doc__ or "").lower()
