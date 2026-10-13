import json
import logging

import httpx
import pytest

from app.config import DEFAULT_CANARIES, Settings
from app.events import EventBus
from app.network_meter import NetworkMeter
from app.orchestrator import Orchestrator
from app.providers import ProviderUnavailable, build_adapters
from app.providers.base import ProviderError
from app.providers.ollama import OllamaAdapter
from app.providers.openai_like import OpenAIAdapter

DOC = "Project Falcon: acquire Zentra Ltd for USD 212M. Ref BM-7731-KX."
KEY = "sk-test-do-not-leak-123"


def sse(*texts: str) -> bytes:
    lines = [f"data: {json.dumps({'choices': [{'delta': {'content': t}}]})}\n\n" for t in texts]
    return ("".join(lines) + "data: [DONE]\n\n").encode()


def ndjson(*texts: str) -> bytes:
    lines = [json.dumps({"message": {"content": t}, "done": False}) for t in texts]
    lines.append(json.dumps({"message": {"content": ""}, "done": True}))
    return "\n".join(lines).encode()


def recorder(status: int, body: bytes):
    seen: list[httpx.Request] = []

    def handler(request):
        seen.append(request)
        return httpx.Response(status, content=body)

    return httpx.MockTransport(handler), seen


def meter(events=None):
    return NetworkMeter("p", (events if events is not None else []).append, DEFAULT_CANARIES)


async def collect(adapter, m=None):
    return "".join([t async for t in adapter.stream("Summarise", DOC, m or meter())])


# OpenAI


async def test_openai_streams_and_sends_document(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", KEY)
    transport, seen = recorder(200, sse("Hello", " world"))
    events: list[dict] = []
    m = meter(events)
    text = await collect(OpenAIAdapter("https://api.openai.com/v1", "gpt-test", transport=transport), m)

    assert text == "Hello world"
    req = seen[0]
    assert str(req.url) == "https://api.openai.com/v1/chat/completions"
    assert req.headers["authorization"] == f"Bearer {KEY}"
    body = json.loads(req.content)
    assert body["model"] == "gpt-test" and body["stream"] is True
    assert DOC in body["messages"][0]["content"]
    assert m.external_bytes_out > len(DOC)
    [payload] = [e for e in events if e["type"] == "payload"]
    assert payload["host"] == "api.openai.com" and len(payload["canary_hits"]) == 4
    assert KEY not in payload["body"]  # payload view shows the body, not headers


async def test_openai_missing_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    transport, seen = recorder(200, sse("x"))
    with pytest.raises(ProviderError, match="OPENAI_API_KEY is not set"):
        await collect(OpenAIAdapter("https://api.openai.com/v1", "m", transport=transport))
    assert seen == []


@pytest.mark.parametrize("status,msg", [(401, "rejected the API key"), (429, "rate limit"), (500, "HTTP 500")])
async def test_openai_http_errors_are_readable_and_safe(monkeypatch, status, msg):
    monkeypatch.setenv("OPENAI_API_KEY", KEY)
    transport, _ = recorder(status, json.dumps({"error": {"message": f"Incorrect API key {KEY}"}}).encode())
    with pytest.raises(ProviderError, match=msg) as exc:
        await collect(OpenAIAdapter("https://api.openai.com/v1", "m", transport=transport))
    assert KEY not in str(exc.value)


async def test_openai_connect_error(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", KEY)

    def refuse(request):
        raise httpx.ConnectError("refused")

    with pytest.raises(ProviderError, match="Cannot reach api.openai.com"):
        await collect(OpenAIAdapter("https://api.openai.com/v1", "m", transport=httpx.MockTransport(refuse)))


# Ollama


async def test_ollama_streams_with_zero_external_bytes():
    transport, seen = recorder(200, ndjson("Local", " answer"))
    events: list[dict] = []
    m = meter(events)
    text = await collect(OllamaAdapter("http://localhost:11434", "qwen2.5:0.5b", transport=transport), m)

    assert text == "Local answer"
    assert str(seen[0].url) == "http://localhost:11434/api/chat"
    assert json.loads(seen[0].content)["model"] == "qwen2.5:0.5b"
    assert m.destinations[("localhost", 11434)].bytes_out > len(DOC)
    assert m.external_bytes_out == 0
    assert not [e for e in events if e["type"] == "payload"]


async def test_ollama_model_not_pulled():
    transport, _ = recorder(404, b'{"error":"model not found"}')
    with pytest.raises(ProviderError, match="ollama pull qwen2.5:0.5b"):
        await collect(OllamaAdapter("http://localhost:11434", "qwen2.5:0.5b", transport=transport))


async def test_ollama_error_mid_stream():
    transport, _ = recorder(200, b'{"message":{"content":"Hi"},"done":false}\n{"error":"out of memory"}\n')
    with pytest.raises(ProviderError, match="out of memory"):
        await collect(OllamaAdapter("http://localhost:11434", "m", transport=transport))


async def test_ollama_not_running():
    def refuse(request):
        raise httpx.ConnectError("refused")

    with pytest.raises(ProviderError, match="not running"):
        await collect(OllamaAdapter("http://localhost:11434", "m", transport=httpx.MockTransport(refuse)))


# Wiring


def test_build_live_adapters():
    adapters = build_adapters(Settings(mode="live", local_model="qwen2.5:0.5b", hosted_model="gpt-x"))
    assert isinstance(adapters["local"], OllamaAdapter) and adapters["local"].model == "qwen2.5:0.5b"
    assert isinstance(adapters["hosted"], OpenAIAdapter) and adapters["hosted"].host == "api.openai.com"


def test_unimplemented_hosted_provider():
    with pytest.raises(ProviderUnavailable):
        build_adapters(Settings(mode="live", hosted_provider="gemini"))


async def test_ac06_no_key_or_document_in_logs(monkeypatch, caplog):
    monkeypatch.setenv("OPENAI_API_KEY", KEY)
    caplog.set_level(logging.DEBUG)
    ok, _ = recorder(200, ndjson("fine"))
    bad, _ = recorder(401, KEY.encode())
    adapters = {
        "local": OllamaAdapter("http://localhost:11434", "m", transport=ok),
        "hosted": OpenAIAdapter("https://api.openai.com/v1", "m", transport=bad),
    }
    results = await Orchestrator(EventBus()).run("r1", "Summarise", DOC, adapters, 5, DEFAULT_CANARIES)
    assert results["local"].state == "done" and results["hosted"].state == "error"
    for secret in (KEY, "Project Falcon", "Zentra Ltd"):
        assert secret not in caplog.text
