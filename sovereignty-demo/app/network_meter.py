"""Per-panel record of where traffic went and what was sent.

Adapters get their HTTP client from `NetworkMeter.client()`. Every request goes through
`MeteredTransport`, which counts bytes per destination (headers plus body, before TLS) and
publishes outbound bodies to external hosts with canary strings tagged.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass

import httpx

from app.canary import find_canaries

LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


def is_external_host(host: str) -> bool:
    return host.lower() not in LOCAL_HOSTS


def _header_bytes(headers: httpx.Headers) -> int:
    return sum(len(k) + len(v) + 4 for k, v in headers.raw) + 2  # "k: v\r\n" per header, blank line


def _request_bytes(request: httpx.Request) -> int:
    start_line = len(request.method) + len(request.url.raw_path) + len(b"  HTTP/1.1\r\n")
    return start_line + _header_bytes(request.headers) + len(request.content)


@dataclass
class Destination:
    host: str
    port: int
    external: bool
    bytes_out: int = 0
    bytes_in: int = 0


class NetworkMeter:
    def __init__(self, panel: str, emit: Callable[[dict], None], canaries: list[str] | None = None) -> None:
        self.panel = panel
        self._emit = emit
        self.canaries = list(canaries or [])
        self.destinations: dict[tuple[str, int], Destination] = {}

    @property
    def external_bytes_out(self) -> int:
        return sum(d.bytes_out for d in self.destinations.values() if d.external)

    def client(self, *, transport: httpx.AsyncBaseTransport | None = None, **kwargs) -> httpx.AsyncClient:
        """An httpx client whose traffic is counted. `transport` is the inner transport (tests, mocks)."""
        inner = transport or httpx.AsyncHTTPTransport()
        return httpx.AsyncClient(transport=MeteredTransport(self, inner), **kwargs)

    def record(self, host: str, port: int, *, bytes_out: int = 0, bytes_in: int = 0) -> None:
        key = (host, port)
        dest = self.destinations.get(key)
        if dest is None:
            dest = self.destinations[key] = Destination(host, port, is_external_host(host))
        dest.bytes_out += bytes_out
        dest.bytes_in += bytes_in
        self._emit({
            "type": "net",
            "panel": self.panel,
            "host": dest.host,
            "port": dest.port,
            "bytes_out": dest.bytes_out,
            "bytes_in": dest.bytes_in,
            "external": dest.external,
            "external_bytes_out": self.external_bytes_out,
        })

    def capture_payload(self, host: str, body: str) -> None:
        """Publish an outbound body as sent by the app, before TLS. Local hosts are skipped."""
        if not is_external_host(host):
            return
        self._emit({
            "type": "payload",
            "panel": self.panel,
            "host": host,
            "body": body,
            "canary_hits": find_canaries(body, self.canaries),
        })


class MeteredTransport(httpx.AsyncBaseTransport):
    """Counts a request once it has been delivered (response headers received), then counts
    response bytes as they stream in. A request that fails to connect counts as nothing sent."""

    def __init__(self, meter: NetworkMeter, inner: httpx.AsyncBaseTransport) -> None:
        self.meter = meter
        self.inner = inner

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        await request.aread()
        response = await self.inner.handle_async_request(request)
        host, port = request.url.host, request.url.port or (443 if request.url.scheme == "https" else 80)
        self.meter.record(host, port, bytes_out=_request_bytes(request), bytes_in=_header_bytes(response.headers))
        self.meter.capture_payload(host, request.content.decode("utf-8", errors="replace"))
        if response.is_stream_consumed:  # body supplied up front, already read by httpx
            self.meter.record(host, port, bytes_in=len(response.content))
        else:
            response.stream = _CountingStream(response.stream, lambda n: self.meter.record(host, port, bytes_in=n))
        return response

    async def aclose(self) -> None:
        await self.inner.aclose()


class _CountingStream(httpx.AsyncByteStream):
    def __init__(self, inner: httpx.AsyncByteStream, on_chunk: Callable[[int], None]) -> None:
        self.inner = inner
        self.on_chunk = on_chunk

    async def __aiter__(self) -> AsyncIterator[bytes]:
        async for chunk in self.inner:
            self.on_chunk(len(chunk))
            yield chunk

    async def aclose(self) -> None:
        await self.inner.aclose()
