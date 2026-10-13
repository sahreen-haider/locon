import asyncio
import time

from fastapi.testclient import TestClient

from app.config import Settings
from app.events import EventBus
from app.main import create_app
from app.network_meter import NetworkMeter
from app.orchestrator import Orchestrator
from app.providers import build_adapters
from app.providers.mock import HOSTED_ANSWER, LOCAL_ANSWER, MockAdapter

DOC = "Project Falcon: acquire Zentra Ltd for USD 212M. Ref BM-7731-KX."


def drain(queue: asyncio.Queue) -> list[dict]:
    events = []
    while not queue.empty():
        events.append(queue.get_nowait())
    return events


class HangingAdapter:
    name, model, host, is_external = "Hangs", "hang", "api.slow.example", True

    async def stream(self, prompt, document, meter):
        await asyncio.sleep(3600)
        yield ""


class FailingAdapter:
    name, model, host, is_external = "Fails", "fail", "api.broken.example", True

    async def stream(self, prompt, document, meter):
        raise ConnectionError("provider unreachable")
        yield ""


async def test_ac01_mock_run_streams_both_panels(no_network, mock_settings):
    bus = EventBus()
    queue = bus.subscribe()
    results = await Orchestrator(bus).run("r1", "Summarise", DOC, build_adapters(mock_settings), 5)
    events = drain(queue)

    assert results["local"].state == results["hosted"].state == "done"
    assert results["local"].text == LOCAL_ANSWER
    assert results["hosted"].text == HOSTED_ANSWER
    for panel in ("local", "hosted"):
        tokens = [e for e in events if e["type"] == "token" and e["panel"] == panel]
        assert len(tokens) > 10
        states = [e["state"] for e in events if e["type"] == "status" and e["panel"] == panel]
        assert states == ["running", "done"]
        metrics = [e for e in events if e["type"] == "metrics" and e["panel"] == panel]
        assert metrics[0]["ttft_ms"] is not None and metrics[0]["total_ms"] >= metrics[0]["ttft_ms"]
    assert all(e["run_id"] == "r1" for e in events)


async def test_ac02_ac03_mock_run_counters_and_payload(no_network, mock_settings):
    bus = EventBus()
    queue = bus.subscribe()
    results = await Orchestrator(bus).run(
        "r1", "Summarise", DOC, build_adapters(mock_settings), 5, mock_settings.canaries
    )
    events = drain(queue)

    # AC-02: local traffic exists but none of it is external
    assert results["local"].external_bytes_out == 0
    assert results["local"].destinations[0]["bytes_out"] > 0
    assert all(not e["external"] for e in events if e["type"] == "net" and e["panel"] == "local")
    # AC-03: hosted sends the document out, and the payload view tags the canaries
    assert results["hosted"].external_bytes_out > len(DOC)
    payloads = [e for e in events if e["type"] == "payload"]
    assert [p["panel"] for p in payloads] == ["hosted"]
    hits = payloads[0]["canary_hits"]
    assert {h["text"] for h in hits} == set(mock_settings.canaries)
    assert all(payloads[0]["body"][h["start"]:h["end"]] == h["text"] for h in hits)


async def test_panels_run_concurrently():
    adapters = build_adapters(Settings(mode="mock", mock_token_delay_s=0.01))
    start = time.perf_counter()
    await Orchestrator(EventBus()).run("r1", "q", DOC, adapters, 5)
    elapsed = time.perf_counter() - start
    serial = sum(len(a.answer.split()) * a.token_delay_s for a in adapters.values())
    assert elapsed < serial * 0.75


async def test_hung_panel_times_out_without_blocking_other(mock_settings):
    adapters = {"local": build_adapters(mock_settings)["local"], "hosted": HangingAdapter()}
    results = await Orchestrator(EventBus()).run("r1", "q", DOC, adapters, timeout_s=0.3)
    assert results["local"].state == "done"
    assert results["hosted"].state == "error"
    assert "0.3 seconds" in results["hosted"].detail


async def test_failing_panel_is_isolated(mock_settings):
    adapters = {"local": build_adapters(mock_settings)["local"], "hosted": FailingAdapter()}
    results = await Orchestrator(EventBus()).run("r1", "q", DOC, adapters, 5)
    assert results["local"].state == "done"
    assert results["hosted"].state == "error"
    assert results["hosted"].detail == "provider unreachable"


async def test_mock_adapter_is_deterministic():
    adapter = build_adapters(Settings(mode="mock", mock_token_delay_s=0))["hosted"]
    assert isinstance(adapter, MockAdapter)

    runs = ["".join([c async for c in adapter.stream("q", DOC, NetworkMeter("hosted", lambda e: None))]) for _ in range(2)]
    assert runs[0] == runs[1] == HOSTED_ANSWER


def test_ac01_end_to_end_over_websocket(no_network, mock_settings):
    with TestClient(create_app(mock_settings)) as client, client.websocket_connect("/ws") as ws:
        assert ws.receive_json()["type"] == "config"
        resp = client.post("/api/run", json={"prompt": "Summarise the risks", "document_id": "memo_small"})
        assert resp.status_code == 200
        run_id = resp.json()["run_id"]

        done, tokens = set(), {"local": 0, "hosted": 0}
        while done != {"local", "hosted"}:
            event = ws.receive_json()
            assert event["run_id"] == run_id
            if event["type"] == "token":
                tokens[event["panel"]] += 1
            if event["type"] == "payload":
                assert event["panel"] == "hosted" and event["canary_hits"]
            if event["type"] == "status" and event["state"] == "done":
                done.add(event["panel"])
        assert tokens["local"] > 0 and tokens["hosted"] > 0


def test_run_unknown_document_404(mock_settings):
    with TestClient(create_app(mock_settings)) as client:
        assert client.post("/api/run", json={"prompt": "q", "document_id": "../app/main"}).status_code == 404


def test_unimplemented_hosted_provider_returns_409(mock_settings):
    mock_settings.hosted_provider = "anthropic"
    with TestClient(create_app(mock_settings)) as client:
        resp = client.post("/api/run", json={"prompt": "q", "document_id": "memo_small", "mode": "live"})
        assert resp.status_code == 409
