import httpx
import pytest

from app.config import DEFAULT_CANARIES
from app.network_meter import NetworkMeter, is_external_host

REPLY = b"x" * 500


def ok(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, content=REPLY)


def make_meter():
    events: list[dict] = []
    return NetworkMeter("hosted", events.append, DEFAULT_CANARIES), events


async def post(meter, url, body: bytes, handler=ok):
    async with meter.client(transport=httpx.MockTransport(handler)) as client:
        return (await client.post(url, content=body)).content


@pytest.mark.parametrize("host,external", [("localhost", False), ("127.0.0.1", False), ("::1", False),
                                           ("LOCALHOST", False), ("api.openai.com", True), ("10.0.0.5", True)])
def test_external_classification(host, external):
    assert is_external_host(host) is external


async def test_bytes_out_tracks_body_size():
    meter, _ = make_meter()
    await post(meter, "https://api.a.example/v1", b"a" * 1000)
    first = meter.destinations[("api.a.example", 443)].bytes_out
    await post(meter, "https://api.a.example/v1", b"a" * 2000)
    second = meter.destinations[("api.a.example", 443)].bytes_out - first
    assert second - first == 1000
    assert first > 1000  # headers and request line count too


async def test_streamed_response_bytes_are_counted():
    meter, _ = make_meter()
    await post(meter, "https://api.a.example/v1", b"{}")
    assert meter.destinations[("api.a.example", 443)].bytes_in > len(REPLY)

    async def chunks():
        for _ in range(5):
            yield b"y" * 100

    async with meter.client(transport=httpx.MockTransport(lambda r: httpx.Response(200, content=chunks()))) as client:
        async with client.stream("POST", "https://api.b.example/v1", content=b"{}") as resp:
            received = sum([len(c) async for c in resp.aiter_bytes()])
    assert received == 500
    assert meter.destinations[("api.b.example", 443)].bytes_in >= 500


async def test_counts_are_per_host_and_port():
    meter, _ = make_meter()
    await post(meter, "https://api.a.example/v1", b"1")
    await post(meter, "https://api.a.example/v1", b"2")
    await post(meter, "https://api.b.example/v1", b"3")
    await post(meter, "http://localhost:11434/api/chat", b"4")
    assert set(meter.destinations) == {("api.a.example", 443), ("api.b.example", 443), ("localhost", 11434)}
    a, b = meter.destinations[("api.a.example", 443)], meter.destinations[("api.b.example", 443)]
    assert a.bytes_out > b.bytes_out > 0
    assert meter.external_bytes_out == a.bytes_out + b.bytes_out


async def test_ac02_localhost_is_zero_external_bytes():
    meter, events = make_meter()
    await post(meter, "http://localhost:11434/api/chat", b"Project Falcon and Zentra Ltd")
    assert meter.destinations[("localhost", 11434)].bytes_out > 0
    assert meter.external_bytes_out == 0
    assert all(e["external"] is False for e in events if e["type"] == "net")
    assert not [e for e in events if e["type"] == "payload"]


async def test_ac03_external_payload_captured_with_canaries():
    meter, events = make_meter()
    body = b'{"content": "Board memo: Project Falcon, Zentra Ltd, USD 212M"}'
    await post(meter, "https://api.hosted.example/v1/chat", body)
    assert meter.external_bytes_out > len(body)
    [payload] = [e for e in events if e["type"] == "payload"]
    assert payload["body"] == body.decode()
    assert {h["text"] for h in payload["canary_hits"]} == {"Project Falcon", "Zentra Ltd", "USD 212M"}


async def test_failed_connection_counts_nothing_sent():
    def refuse(request):
        raise httpx.ConnectError("connection refused")

    meter, events = make_meter()
    with pytest.raises(httpx.ConnectError):
        await post(meter, "https://api.hosted.example/v1/chat", b"Project Falcon", handler=refuse)
    assert meter.external_bytes_out == 0
    assert events == []
