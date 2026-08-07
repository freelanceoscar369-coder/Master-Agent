"""The one place this package touches the network (Mission Brief 033).

Everything else in `providers/` is pure logic over what a transport
returns. That split is what makes several hundred tests possible without a
running daemon, and it is the same shape MB030 used for `SystemProbe` and
MB024 for `ExecutiveGateway`: a small protocol, one real implementation,
and a fake in tests.

`urllib` rather than `httpx` deliberately. It is stdlib, so the first
production AI execution path in Kalpavriksha adds **no new dependency**,
and the surface used here — one POST, one GET, both JSON — does not earn
one. `httpx` is already a project dependency and can replace this behind
the same protocol whenever streaming or connection pooling is worth
having; nothing above this module would change.

**No retry policy lives here.** A transport reports what happened; how
many times to try is the provider's business (MB033 Rule 4), and burying a
retry loop underneath a provider is how "no retries beyond its own
transport layer" quietly becomes six.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

#: Long by default because a local model on a laptop CPU genuinely takes
#: this long to think, and a timeout shorter than the work turns a working
#: system into a broken-looking one.
DEFAULT_TIMEOUT_SECONDS = 120.0


class TransportError(Exception):
    """Base: something went wrong below the application layer."""


class TransportUnavailable(TransportError):
    """Nothing is listening — refused, unresolvable, or unroutable."""


class TransportTimeout(TransportError):
    """Something is listening and did not answer in time."""


@dataclass(frozen=True)
class HttpResponse:
    """A response, whatever its status. A 404 is an answer, not an error:
    "that model is not installed" arrives as one, and turning it into an
    exception would lose the body that says so."""

    status: int
    body: str

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 300

    def json(self) -> Any:
        """Raises `ValueError` on a body that is not JSON. The caller
        turns that into a `MALFORMED` result — this module does not decide
        what a bad body means."""
        return json.loads(self.body)


@runtime_checkable
class Transport(Protocol):
    """What a provider needs from the network, and nothing more."""

    def post_json(
        self, url: str, payload: dict[str, Any], timeout: float
    ) -> HttpResponse: ...

    def get(self, url: str, timeout: float) -> HttpResponse: ...

    def stream_json(
        self, url: str, payload: dict[str, Any], timeout: float
    ) -> Iterator[str]: ...


class UrllibTransport:
    """The real network. Every method translates a stdlib exception into
    one of exactly two transport failures, so no caller ever has to know
    what `URLError` is."""

    def post_json(
        self,
        url: str,
        payload: dict[str, Any],
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> HttpResponse:
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        return self._open(request, timeout)

    def get(self, url: str, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> HttpResponse:
        request = urllib.request.Request(url, method="GET")
        return self._open(request, timeout)

    def stream_json(
        self,
        url: str,
        payload: dict[str, Any],
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> Iterator[str]:
        """One POST, yielding NDJSON lines as they arrive (MB038).

        `timeout` is the **socket read timeout**: how long a single read
        may block. It is mechanism, not policy -- this module has no idea
        what a TTFT budget is, and deciding when a stream has taken too
        long belongs to the adapter that was handed a `CallBudget`.

        Yields raw lines rather than parsed objects for the same reason
        `post_json` returns a body rather than a decoded payload: what a
        malformed line *means* is the caller's decision, and a transport
        that raised on one would deny the caller the text that explains
        why.
        """
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        self._guard(request)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as handle:
                for raw in handle:
                    line = raw.decode("utf-8", "replace").strip()
                    if line:
                        yield line
        except urllib.error.HTTPError as exc:
            # A streaming request that fails outright still answers, and
            # the body says why ("model not found"). Surfaced as one line
            # so the caller reads it through the same path as any other.
            body = ""
            try:
                body = exc.read().decode("utf-8", "replace")
            except Exception:  # noqa: BLE001 - a body we cannot read is no body
                body = ""
            raise TransportUnavailable(f"HTTP {exc.code}: {body}".strip()) from exc
        except TimeoutError as exc:
            raise TransportTimeout(f"no answer within {timeout:g}s") from exc
        except urllib.error.URLError as exc:
            reason = getattr(exc, "reason", exc)
            if isinstance(reason, TimeoutError):
                raise TransportTimeout(f"no answer within {timeout:g}s") from exc
            raise TransportUnavailable(str(reason)) from exc
        except OSError as exc:
            raise TransportUnavailable(str(exc)) from exc

    def _guard(self, request: Any) -> None:
        if request.full_url.split(":", 1)[0] not in ("http", "https"):
            # `urlopen` will happily open `file://`. A provider base URL is
            # configuration, and configuration that can read the disk
            # through an HTTP client is a hole nobody would look for.
            raise TransportUnavailable(f"refusing non-http URL: {request.full_url}")

    def _open(self, request: Any, timeout: float) -> HttpResponse:
        self._guard(request)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as handle:
                return HttpResponse(
                    status=handle.status, body=handle.read().decode("utf-8", "replace")
                )
        except urllib.error.HTTPError as exc:
            # An HTTP error carries a body worth keeping -- "model not
            # found" arrives this way.
            body = ""
            try:
                body = exc.read().decode("utf-8", "replace")
            except Exception:  # noqa: BLE001 - a body we cannot read is no body
                body = ""
            return HttpResponse(status=exc.code, body=body)
        except TimeoutError as exc:
            raise TransportTimeout(f"no answer within {timeout:g}s") from exc
        except urllib.error.URLError as exc:
            reason = getattr(exc, "reason", exc)
            if isinstance(reason, TimeoutError):
                raise TransportTimeout(f"no answer within {timeout:g}s") from exc
            raise TransportUnavailable(str(reason)) from exc
        except OSError as exc:
            raise TransportUnavailable(str(exc)) from exc
